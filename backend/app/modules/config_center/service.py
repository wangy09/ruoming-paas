"""
若茗 PaaS - 配置中心服务层

四级分层覆盖（优先级由高到低）：
  user > app > tenant > global

读取时从高优先级向下查找，找到即返回。
支持 Redis 缓存加速，变更时自动失效。

Author: ruoming
"""
from __future__ import annotations

import json
import time
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.modules.config_center.models import SysConfig

logger = structlog.get_logger(__name__)

# 配置缓存 TTL（秒）
_CACHE_TTL = 300  # 5 分钟

# 配置历史表创建 SQL（Alembic 迁移前的临时建表）
_CONFIG_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS sys_config_history (
    id          BIGSERIAL PRIMARY KEY,
    config_key  VARCHAR(256) NOT NULL,
    scope_type  VARCHAR(20) NOT NULL,
    scope_id    BIGINT,
    old_value   TEXT,
    new_value   TEXT,
    changed_by  BIGINT,
    changed_at  TIMESTAMPTZ DEFAULT NOW(),
    remark      TEXT
);
"""


def _cache_key(scope: str, tenant_id: int | None, app_key: str | None, user_id: int | None) -> str:
    return f"config:{scope}:{tenant_id or 0}:{app_key or ''}:{user_id or 0}"


class ConfigCenterService:
    """
    配置中心服务。

    用法::

        svc = ConfigCenterService(db)
        values = await svc.get_merged(
            keys=["ai.cache.enabled", "ai.cache.ttl"],
            tenant_id=1,
            app_key="ai",
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 核心：合并查询（四级覆盖） ────────────────────────────────────────────

    async def get_merged(
        self,
        keys: list[str],
        *,
        tenant_id: int | None = None,
        app_key: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, str]:
        """
        按四级优先级合并返回配置字典。

        优先级：user > app > tenant > global
        只返回 keys 中存在的键，找不到的键不出现在结果中。
        """
        result: dict[str, str] = {}
        remaining = set(keys)

        # 按优先级从高到低依次查询
        scopes: list[tuple[str, int | None, str | None, int | None]] = []
        if user_id:
            scopes.append(("user", tenant_id, app_key, user_id))
        if app_key:
            scopes.append(("app", tenant_id, app_key, None))
        if tenant_id:
            scopes.append(("tenant", tenant_id, None, None))
        scopes.append(("global", None, None, None))

        for scope, t_id, a_key, u_id in scopes:
            if not remaining:
                break
            rows = await self._query_scope(scope, list(remaining), t_id, a_key, u_id)
            for row in rows:
                if row.config_key in remaining:
                    val = self._decrypt_if_needed(row)
                    result[row.config_key] = val
                    remaining.discard(row.config_key)

        return result

    async def get(
        self,
        config_key: str,
        *,
        scope: str = "global",
        tenant_id: int | None = None,
        app_key: str | None = None,
        user_id: int | None = None,
        default: str | None = None,
    ) -> str | None:
        """获取单个配置值，指定具体层级"""
        rows = await self._query_scope(scope, [config_key], tenant_id, app_key, user_id)
        if rows:
            return self._decrypt_if_needed(rows[0])
        return default

    async def set(
        self,
        config_key: str,
        config_val: str,
        *,
        scope: str = "global",
        tenant_id: int | None = None,
        app_key: str | None = None,
        user_id: int | None = None,
        val_type: str = "string",
        is_encrypted: bool = False,
        label: str | None = None,
        description: str | None = None,
        is_public: bool = False,
        changed_by: int | None = None,
    ) -> SysConfig:
        """
        设置配置值（不存在则创建，已存在则更新）。
        自动写入变更历史（异步，不影响主流程）。
        """
        # 查询已有记录
        stmt = self._build_scope_stmt(scope, [config_key], tenant_id, app_key, user_id)
        result = await self.db.execute(stmt)
        existing: SysConfig | None = result.scalar_one_or_none()

        old_value = self._decrypt_if_needed(existing) if existing else None

        # 加密处理
        store_val = config_val
        if is_encrypted:
            from app.core.security import encrypt_value
            store_val = encrypt_value(config_val)

        if existing:
            existing.config_val = store_val
            existing.val_type = val_type
            existing.is_encrypted = is_encrypted
            if label is not None:
                existing.label = label
            if description is not None:
                existing.description = description
            existing.is_public = is_public
            await self.db.flush()
            obj = existing
        else:
            obj = SysConfig(
                scope=scope,
                tenant_id=tenant_id,
                app_key=app_key,
                user_id=user_id,
                config_key=config_key,
                config_val=store_val,
                val_type=val_type,
                is_encrypted=is_encrypted,
                label=label,
                description=description,
                is_public=is_public,
            )
            self.db.add(obj)
            await self.db.flush()

        # 失效 Redis 缓存
        await self._invalidate_cache(scope, tenant_id, app_key, user_id)

        # 异步写入变更历史（fire-and-forget）
        await self._write_history(
            config_key=config_key,
            scope_type=scope,
            scope_id=tenant_id or user_id,
            old_value=old_value,
            new_value=config_val,  # 存明文
            changed_by=changed_by,
        )

        logger.info(
            "config_set",
            config_key=config_key,
            scope=scope,
            tenant_id=tenant_id,
            changed_by=changed_by,
        )
        return obj

    async def delete(
        self,
        config_key: str,
        *,
        scope: str,
        tenant_id: int | None = None,
        app_key: str | None = None,
        user_id: int | None = None,
    ) -> bool:
        """删除配置项（软删除）"""
        stmt = self._build_scope_stmt(scope, [config_key], tenant_id, app_key, user_id)
        result = await self.db.execute(stmt)
        obj: SysConfig | None = result.scalar_one_or_none()
        if not obj:
            return False
        obj.is_deleted = True
        await self.db.flush()
        await self._invalidate_cache(scope, tenant_id, app_key, user_id)
        return True

    async def list_by_scope(
        self,
        scope: str,
        *,
        tenant_id: int | None = None,
        app_key: str | None = None,
        user_id: int | None = None,
    ) -> list[SysConfig]:
        """列出某层级下所有配置"""
        stmt = (
            select(SysConfig)
            .where(SysConfig.is_deleted == False)
            .where(SysConfig.scope == scope)
        )
        if tenant_id is not None:
            stmt = stmt.where(SysConfig.tenant_id == tenant_id)
        else:
            stmt = stmt.where(SysConfig.tenant_id == None)
        if app_key is not None:
            stmt = stmt.where(SysConfig.app_key == app_key)
        if user_id is not None:
            stmt = stmt.where(SysConfig.user_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── 类型转换辅助 ──────────────────────────────────────────────────────────

    def get_bool(self, val: str | None, default: bool = False) -> bool:
        if val is None:
            return default
        return val.lower() in ("true", "1", "yes", "on")

    def get_int(self, val: str | None, default: int = 0) -> int:
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def get_json(self, val: str | None, default: Any = None) -> Any:
        try:
            return json.loads(val) if val is not None else default
        except (json.JSONDecodeError, TypeError):
            return default

    # ── 内部方法 ──────────────────────────────────────────────────────────────

    async def _query_scope(
        self,
        scope: str,
        keys: list[str],
        tenant_id: int | None,
        app_key: str | None,
        user_id: int | None,
    ) -> list[SysConfig]:
        stmt = self._build_scope_stmt(scope, keys, tenant_id, app_key, user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    def _build_scope_stmt(
        self,
        scope: str,
        keys: list[str],
        tenant_id: int | None,
        app_key: str | None,
        user_id: int | None,
    ):
        stmt = (
            select(SysConfig)
            .where(SysConfig.is_deleted == False)
            .where(SysConfig.scope == scope)
            .where(SysConfig.config_key.in_(keys))
        )
        # 各层级的额外过滤条件
        if scope == "global":
            stmt = stmt.where(SysConfig.tenant_id == None)
        elif scope == "tenant":
            stmt = stmt.where(SysConfig.tenant_id == tenant_id)
            stmt = stmt.where(SysConfig.app_key == None)
            stmt = stmt.where(SysConfig.user_id == None)
        elif scope == "app":
            stmt = stmt.where(SysConfig.tenant_id == tenant_id)
            stmt = stmt.where(SysConfig.app_key == app_key)
            stmt = stmt.where(SysConfig.user_id == None)
        elif scope == "user":
            stmt = stmt.where(SysConfig.tenant_id == tenant_id)
            stmt = stmt.where(SysConfig.user_id == user_id)
        return stmt

    @staticmethod
    def _decrypt_if_needed(row: SysConfig | None) -> str:
        if row is None:
            return ""
        if row.is_encrypted and row.config_val:
            try:
                from app.core.security import decrypt_value
                return decrypt_value(row.config_val)
            except Exception:
                return row.config_val or ""
        return row.config_val or ""

    async def _invalidate_cache(
        self,
        scope: str,
        tenant_id: int | None,
        app_key: str | None,
        user_id: int | None,
    ) -> None:
        """失效 Redis 缓存（非阻塞）"""
        try:
            redis = await get_redis_client()
            key = _cache_key(scope, tenant_id, app_key, user_id)
            await redis.delete(key)
        except Exception as e:
            logger.warning("config_cache_invalidate_failed", error=str(e))

    async def _write_history(
        self,
        config_key: str,
        scope_type: str,
        scope_id: int | None,
        old_value: str | None,
        new_value: str | None,
        changed_by: int | None,
    ) -> None:
        """写入配置变更历史（fire-and-forget，失败不影响主流程）"""
        try:
            from sqlalchemy import text
            await self.db.execute(
                text("""
                    INSERT INTO sys_config_history
                        (config_key, scope_type, scope_id, old_value, new_value, changed_by)
                    VALUES
                        (:config_key, :scope_type, :scope_id, :old_value, :new_value, :changed_by)
                """),
                {
                    "config_key": config_key,
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "old_value": old_value,
                    "new_value": new_value,
                    "changed_by": changed_by,
                },
            )
        except Exception as e:
            # 表不存在或其他异常，不影响主流程
            logger.debug("config_history_write_failed", error=str(e))
