"""
若茗 PaaS - 认证服务
包含：登录、Refresh Token 轮换、登出、登录安全保护
Author: ruoming
"""
import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.error_codes import UserErrCode
from app.core.exceptions import (
    AccountLockedException,
    AuthException,
    BusinessException,
    RefreshTokenInvalidException,
)
from app.core.redis import RedisKeys
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_api_key,
    verify_password,
)
from app.modules.audit.service import AuditService
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenResponse,
)
from app.modules.user.models import SysUser

logger = structlog.get_logger(__name__)


class AuthService:
    """认证服务"""

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self.db = db
        self.redis = redis

    async def login(self, req: LoginRequest, client_ip: str | None = None, user_agent: str | None = None) -> LoginResponse:
        """
        用户名/密码登录。

        流程：
        1. 查找用户（支持用户名或邮箱）
        2. 校验账号锁定状态
        3. 校验密码
        4. 密码错误累计，达到阈值锁定账号
        5. 颁发 Access Token + Refresh Token
        6. 异步记录登录日志
        """
        # 1. 查找用户
        result = await self.db.execute(
            select(SysUser).where(
                (SysUser.username == req.username) | (SysUser.email == req.username),
                SysUser.is_deleted == False,  # noqa: E712
            )
        )
        user = result.scalar_one_or_none()

        # 2. 账号不存在，也要检查锁定（防止枚举攻击时信息泄漏）
        if not user:
            # 仍然记录失败日志，但不泄漏"用户不存在"
            asyncio.create_task(
                self._record_login_log(
                    user_id=None,
                    username=req.username,
                    status=0,
                    fail_reason="用户名或密码错误",
                    login_ip=client_ip,
                    user_agent=user_agent,
                )
            )
            raise BusinessException(
                code=UserErrCode.WRONG_PASSWORD,
                message="用户名或密码错误",
                http_status=400,
            )

        # 3. 校验账号锁定
        if user.locked_until and user.locked_until > datetime.now(UTC):
            unlock_time = user.locked_until.strftime("%H:%M:%S")
            raise AccountLockedException(f"账号已被锁定，请在 {unlock_time} 后重试")

        # 4. 校验账号状态
        if not user.status:
            raise BusinessException(
                code=UserErrCode.USER_DISABLED,
                message="账号已被禁用，请联系管理员",
                http_status=403,
            )

        # 5. 校验密码
        if not verify_password(req.password, user.password):
            await self._handle_login_failure(user, client_ip, user_agent)
            raise BusinessException(
                code=UserErrCode.WRONG_PASSWORD,
                message="用户名或密码错误",
                http_status=400,
            )

        # 6. 登录成功，重置失败计数
        if user.login_fail_count > 0:
            await self.db.execute(
                update(SysUser)
                .where(SysUser.id == user.id)
                .values(
                    login_fail_count=0,
                    locked_until=None,
                    last_login=datetime.now(UTC),
                    last_login_ip=client_ip,
                )
            )

        # 7. 颁发 Token
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            is_superplatform=user.is_superplatform,
            extra={"username": user.username},
        )
        refresh_token, jti = create_refresh_token(user.id)

        # 8. 存储 Refresh Token 到 Redis 白名单
        refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        await self.redis.setex(
            RedisKeys.REFRESH_TOKEN.format(jti=jti),
            refresh_ttl,
            str(user.id),
        )

        # 9. 异步记录登录日志
        asyncio.create_task(
            self._record_login_log(
                user_id=user.id,
                username=user.username,
                status=1,
                login_ip=client_ip,
                user_agent=user_agent,
            )
        )

        logger.info("user_login_success", user_id=user.id, username=user.username)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user.id,
            username=user.username,
            nickname=user.nickname,
            is_superplatform=user.is_superplatform,
            tenant_id=user.tenant_id,
        )

    async def refresh_token(self, raw_refresh_token: str) -> RefreshTokenResponse:
        """
        Refresh Token 轮换（Rotation）。

        安全机制：
        - 每次使用 Refresh Token 后，旧 Token 立即失效
        - 颁发新的 Refresh Token（防止重放攻击）
        - 若检测到已失效的 Token 被使用，视为 Token 泄露，强制退出所有会话
        """
        payload = decode_refresh_token(raw_refresh_token)
        user_id = int(payload["sub"])
        jti = payload["jti"]

        # 校验 Refresh Token 是否在 Redis 白名单中
        redis_key = RedisKeys.REFRESH_TOKEN.format(jti=jti)
        stored = await self.redis.get(redis_key)

        if stored is None:
            # Token 已被消耗或不存在，可能是重放攻击
            logger.warning("refresh_token_reuse_detected", user_id=user_id, jti=jti)
            # 安全措施：清除该用户所有 Refresh Token
            await self._revoke_all_user_tokens(user_id)
            raise RefreshTokenInvalidException()

        if int(stored) != user_id:
            raise RefreshTokenInvalidException()

        # 删除旧 Token（轮换：每个 Token 只能用一次）
        await self.redis.delete(redis_key)

        # 获取最新用户信息
        result = await self.db.execute(
            select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
        )
        user = result.scalar_one_or_none()
        if not user or not user.status:
            raise AuthException("用户不存在或已禁用")

        # 颁发新 Token
        new_access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            is_superplatform=user.is_superplatform,
            extra={"username": user.username},
        )
        new_refresh_token, new_jti = create_refresh_token(user.id)

        # 存储新 Refresh Token
        refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        await self.redis.setex(
            RedisKeys.REFRESH_TOKEN.format(jti=new_jti),
            refresh_ttl,
            str(user.id),
        )

        logger.info("token_refreshed", user_id=user.id)

        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, user_id: int, refresh_token: str | None = None) -> None:
        """
        登出：撤销 Refresh Token。
        如果提供了 refresh_token，则仅撤销该 Token（单设备登出）。
        否则撤销该用户所有 Token（所有设备登出）。
        """
        if refresh_token:
            try:
                payload = decode_refresh_token(refresh_token)
                jti = payload["jti"]
                await self.redis.delete(RedisKeys.REFRESH_TOKEN.format(jti=jti))
            except Exception:
                pass  # Token 已过期或无效，忽略
        else:
            await self._revoke_all_user_tokens(user_id)

        logger.info("user_logout", user_id=user_id)

    async def login_with_api_key(self, api_key: str) -> SysUser:
        """
        API Key 认证（三方系统调用）。
        API Key 经过相同的权限校验流程。
        """
        from app.modules.user.models import SysApiKey
        from datetime import UTC

        key_hash = hash_api_key(api_key)
        result = await self.db.execute(
            select(SysApiKey).where(
                SysApiKey.key_hash == key_hash,
                SysApiKey.status == 1,
                SysApiKey.is_deleted == False,  # noqa: E712
            )
        )
        api_key_obj = result.scalar_one_or_none()

        if not api_key_obj:
            raise AuthException("API Key 无效或已被撤销")

        # 校验过期时间
        if api_key_obj.expired_at and api_key_obj.expired_at < datetime.now(UTC):
            raise AuthException("API Key 已过期")

        # 更新最后使用时间（异步，不阻塞请求）
        asyncio.create_task(
            self._update_api_key_last_used(api_key_obj.id)
        )

        # 获取关联用户
        user_result = await self.db.execute(
            select(SysUser).where(
                SysUser.id == api_key_obj.user_id,
                SysUser.is_deleted == False,  # noqa: E712
            )
        )
        user = user_result.scalar_one_or_none()

        if not user or not user.status:
            raise AuthException("API Key 关联的用户不存在或已禁用")

        return user

    # ── 私有方法 ──────────────────────────────────────────────────────

    async def _handle_login_failure(self, user: SysUser, client_ip: str | None, user_agent: str | None = None) -> None:
        """处理登录失败：累计计数，达到阈值锁定账号"""
        new_fail_count = user.login_fail_count + 1
        locked_until = None

        if new_fail_count >= settings.LOGIN_FAIL_MAX_TIMES:
            locked_until = datetime.now(UTC) + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            logger.warning(
                "account_locked",
                user_id=user.id,
                username=user.username,
                fail_count=new_fail_count,
                locked_until=locked_until,
            )

        await self.db.execute(
            update(SysUser)
            .where(SysUser.id == user.id)
            .values(login_fail_count=new_fail_count, locked_until=locked_until)
        )

        # 记录失败日志（异步）
        asyncio.create_task(
            self._record_login_log(
                user_id=user.id,
                username=user.username,
                status=0,
                fail_reason="密码错误" if new_fail_count < settings.LOGIN_FAIL_MAX_TIMES
                else f"连续{new_fail_count}次失败，账号已锁定",
                login_ip=client_ip,
                user_agent=user_agent,
            )
        )

    async def _revoke_all_user_tokens(self, user_id: int) -> None:
        """撤销用户所有 Refresh Token（通过 scan 删除对应 key）"""
        # 注意：此处用 SCAN 而非 KEYS，避免阻塞 Redis
        pattern = "auth:refresh:*"
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            for key in keys:
                val = await self.redis.get(key)
                if val and int(val) == user_id:
                    await self.redis.delete(key)
            if cursor == 0:
                break

    async def _record_login_log(
        self,
        user_id: int | None,
        username: str,
        status: int,
        fail_reason: str | None = None,
        login_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """记录登录日志（异步任务中调用，使用独立 Session）"""
        try:
            from app.database import AsyncSessionFactory
            async with AsyncSessionFactory() as db:
                svc = AuditService(db)
                await svc.record_login(
                    user_id=user_id,
                    username=username,
                    status=status,
                    fail_reason=fail_reason,
                    login_ip=login_ip,
                    user_agent=user_agent,
                )
                await db.commit()
        except Exception as e:
            logger.error("login_log_record_failed", error=str(e))

    async def _update_api_key_last_used(self, api_key_id: int) -> None:
        """异步更新 API Key 最后使用时间"""
        try:
            from app.database import AsyncSessionFactory
            from app.modules.user.models import SysApiKey
            async with AsyncSessionFactory() as db:
                await db.execute(
                    update(SysApiKey)
                    .where(SysApiKey.id == api_key_id)
                    .values(last_used_at=datetime.now(UTC))
                )
                await db.commit()
        except Exception as e:
            logger.error("api_key_update_failed", error=str(e))
