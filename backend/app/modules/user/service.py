"""
若茗 PaaS - 用户服务
Author: ruoming
"""
import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import UserErrCode
from app.core.exceptions import BusinessException, NotFoundException
from app.core.security import hash_password, verify_password
from app.modules.audit.service import audit_log
from app.modules.permission.models import SysRole, SysUserRole
from app.modules.user.models import SysUser
from app.modules.user.schemas import UserCreate, UserUpdate

logger = structlog.get_logger(__name__)


class UserService:
    """用户服务"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def get_by_id(self, user_id: int) -> SysUser | None:
        """按 ID 获取用户"""
        result = await self.db.execute(
            select(SysUser).where(
                SysUser.id == user_id,
                SysUser.is_deleted == False,  # noqa: E712
            )
        )
        user = result.scalar_one_or_none()
        if user:
            role_result = await self.db.execute(
                select(SysRole.id, SysRole.name, SysRole.code)
                .join(SysUserRole, SysRole.id == SysUserRole.role_id)
                .where(SysUserRole.user_id == user_id)
                .where(SysRole.is_deleted == False)  # noqa: E712
            )
            user.roles = [{"id": r[0], "name": r[1], "code": r[2]} for r in role_result.all()]
        return user

    async def get_list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        status: int | None = None,
        dept_id: int | None = None,
        data_scope: dict | None = None,
    ) -> tuple[list[SysUser], int]:
        """获取用户列表（分页），支持数据权限过滤"""
        from sqlalchemy import func
        from app.modules.integration.models import (
            SysExternalIdentity,
            SysIntegrationConnection,
        )
        from app.modules.system.models import SysDept

        query = select(SysUser, SysDept.name.label("dept_name")).outerjoin(
            SysDept, SysUser.dept_id == SysDept.id
        ).where(SysUser.is_deleted == False)  # noqa: E712

        if self.tenant_id is not None:
            query = query.where(SysUser.tenant_id == self.tenant_id)

        if data_scope:
            allowed_dept_ids = data_scope.get("allowed_dept_ids")
            allowed_user_ids = data_scope.get("allowed_user_ids")
            ds = data_scope.get("data_scope")

            if ds == 5:
                if allowed_user_ids:
                    query = query.where(SysUser.id.in_(allowed_user_ids))
            elif allowed_dept_ids is not None and len(allowed_dept_ids) > 0:
                query = query.where(SysUser.dept_id.in_(allowed_dept_ids))
            elif allowed_dept_ids is not None and len(allowed_dept_ids) == 0:
                return [], 0

        if keyword:
            query = query.where(
                or_(
                    SysUser.username.ilike(f"%{keyword}%"),
                    SysUser.nickname.ilike(f"%{keyword}%"),
                    SysUser.email.ilike(f"%{keyword}%"),
                    SysUser.phone.ilike(f"%{keyword}%"),
                )
            )
        if status is not None:
            query = query.where(SysUser.status == status)
        if dept_id is not None:
            query = query.where(SysUser.dept_id == dept_id)

        count_result = await self.db.execute(
            select(func.count(SysUser.id)).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(SysUser.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        rows = list(result.all())

        user_ids = [row[0].id for row in rows]
        role_map: dict[int, list[dict]] = {uid: [] for uid in user_ids}
        source_map: dict[int, dict] = {}

        if user_ids:
            role_query = (
                select(SysUserRole.user_id, SysRole.id, SysRole.name, SysRole.code)
                .join(SysRole, SysUserRole.role_id == SysRole.id)
                .where(SysUserRole.user_id.in_(user_ids))
                .where(SysRole.is_deleted == False)  # noqa: E712
            )
            role_result = await self.db.execute(role_query)
            for ur_id, r_id, r_name, r_code in role_result.all():
                role_map[ur_id].append({"id": r_id, "name": r_name, "code": r_code})

            source_query = (
                select(
                    SysExternalIdentity.local_id,
                    SysExternalIdentity.provider,
                    SysExternalIdentity.external_id,
                    SysExternalIdentity.connection_id,
                    SysIntegrationConnection.name,
                )
                .outerjoin(
                    SysIntegrationConnection,
                    SysIntegrationConnection.id == SysExternalIdentity.connection_id,
                )
                .where(SysExternalIdentity.local_id.in_(user_ids))
                .where(SysExternalIdentity.identity_type == "user")
                .where(SysExternalIdentity.is_deleted == False)  # noqa: E712
                .order_by(SysExternalIdentity.updated_at.desc())
            )
            source_result = await self.db.execute(source_query)
            for (
                user_id,
                provider,
                external_id,
                connection_id,
                connection_name,
            ) in source_result.all():
                source_map.setdefault(
                    user_id,
                    {
                        "source_type": "external",
                        "source_provider": provider,
                        "source_external_id": external_id,
                        "source_connection_id": connection_id,
                        "source_connection_name": connection_name,
                    },
                )

        items = []
        for user, dept_name in rows:
            user.dept_name = dept_name
            user.roles = role_map.get(user.id, [])
            source = source_map.get(user.id, {"source_type": "local"})
            user.source_type = source.get("source_type")
            user.source_provider = source.get("source_provider")
            user.source_external_id = source.get("source_external_id")
            user.source_connection_id = source.get("source_connection_id")
            user.source_connection_name = source.get("source_connection_name")
            items.append(user)

        return items, total

    @audit_log("user.create", module="user", action="create", resource_type="sys_user")
    async def create_user(self, data: UserCreate) -> SysUser:
        """创建用户"""
        # 校验用户名唯一性
        exists = await self.db.execute(
            select(SysUser.id).where(
                SysUser.username == data.username,
                SysUser.is_deleted == False,  # noqa: E712
            )
        )
        if exists.scalar_one_or_none():
            raise BusinessException(
                code=UserErrCode.USERNAME_EXISTS,
                message=f"用户名 '{data.username}' 已存在",
            )

        # 校验邮箱唯一性
        if data.email:
            email_exists = await self.db.execute(
                select(SysUser.id).where(
                    SysUser.email == data.email,
                    SysUser.is_deleted == False,  # noqa: E712
                )
            )
            if email_exists.scalar_one_or_none():
                raise BusinessException(
                    code=UserErrCode.EMAIL_EXISTS,
                    message="邮箱已被使用",
                )

        user = SysUser(
            username=data.username,
            password=hash_password(data.password),
            nickname=data.nickname or data.username,
            email=data.email or None,  # 空字符串转为 None
            phone=data.phone or None,  # 空字符串转为 None
            dept_id=data.dept_id,
            tenant_id=data.tenant_id or self.tenant_id,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        # 分配角色
        if data.role_ids:
            await self._assign_roles(user.id, data.role_ids)

        logger.info("user_created", user_id=user.id, username=user.username)
        return user

    @audit_log("user.update", module="user", action="update", resource_type="sys_user")
    async def update_user(self, user_id: int, data: UserUpdate) -> SysUser:
        """更新用户信息"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户")

        # 租户权限检查（非超管不能修改其他租户用户）
        if self.tenant_id and user.tenant_id != self.tenant_id:
            raise NotFoundException("用户")

        update_data = data.model_dump(exclude_none=True)
        for k, v in update_data.items():
            # 空字符串转为 None，避免唯一约束冲突
            if isinstance(v, str) and not v:
                v = None
            setattr(user, k, v)

        await self.db.flush()
        await self.db.refresh(user)
        logger.info("user_updated", user_id=user_id)
        return user

    @audit_log("user.delete", module="user", action="delete", resource_type="sys_user")
    async def delete_user(self, user_id: int) -> None:
        """软删除用户"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户")

        if self.tenant_id and user.tenant_id != self.tenant_id:
            raise NotFoundException("用户")

        user.is_deleted = True
        await self.db.flush()
        logger.info("user_deleted", user_id=user_id)

    async def update_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> None:
        """修改密码（需要验证旧密码）"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户")

        if not verify_password(old_password, user.password):
            raise BusinessException(
                code=UserErrCode.OLD_PASSWORD_WRONG,
                message="旧密码错误",
            )

        user.password = hash_password(new_password)
        await self.db.flush()
        logger.info("user_password_changed", user_id=user_id)

    async def reset_password(self, user_id: int, new_password: str) -> None:
        """重置密码（管理员操作，无需验证旧密码）"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户")

        user.password = hash_password(new_password)
        await self.db.flush()
        logger.info("user_password_reset", user_id=user_id)

    async def assign_roles(self, user_id: int, role_ids: list[int]) -> None:
        """给用户分配角色（全量替换）"""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("用户")

        # 删除旧角色关联
        from sqlalchemy import delete
        await self.db.execute(
            delete(SysUserRole).where(SysUserRole.user_id == user_id)
        )

        # 插入新角色关联
        await self._assign_roles(user_id, role_ids)
        logger.info("user_roles_assigned", user_id=user_id, role_ids=role_ids)

    async def _assign_roles(self, user_id: int, role_ids: list[int]) -> None:
        """内部方法：批量插入用户角色关联"""
        for role_id in role_ids:
            # 校验角色是否存在
            role_result = await self.db.execute(
                select(SysRole.id).where(
                    SysRole.id == role_id,
                    SysRole.is_deleted == False,  # noqa: E712
                )
            )
            if role_result.scalar_one_or_none():
                self.db.add(SysUserRole(user_id=user_id, role_id=role_id))
        await self.db.flush()
