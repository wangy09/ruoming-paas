"""
若茗 PaaS - 配置中心服务层

四级分层覆盖（优先级由高到低）：
  user > app > tenant > global

读取时从高优先级向下查找，找到即返回。
支持 Redis 缓存加速，变更时自动失效。

Author: ruoming
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

import structlog
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
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


def _merged_cache_key(
    keys: list[str],
    tenant_id: int | None,
    app_key: str | None,
    user_id: int | None,
    public_only: bool,
) -> str:
    key_text = ",".join(sorted(set(keys)))
    digest = hashlib.sha1(key_text.encode("utf-8")).hexdigest()  # noqa: S324 - cache key only
    public_flag = 1 if public_only else 0
    return f"config:merged:{tenant_id or 0}:{app_key or ''}:{user_id or 0}:{public_flag}:{digest}"


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
        public_only: bool = False,
    ) -> dict[str, str]:
        """
        按四级优先级合并返回配置字典。

        优先级：user > app > tenant > global
        只返回 keys 中存在的键，找不到的键不出现在结果中。
        """
        if not keys:
            return {}

        cached = await self._get_cached_merged(keys, tenant_id, app_key, user_id, public_only)
        if cached is not None:
            logger.debug(
                "config_cache_hit",
                keys=keys,
                tenant_id=tenant_id,
                app_key=app_key,
                user_id=user_id,
                public_only=public_only,
            )
            return cached

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
            rows = await self._query_scope(scope, list(remaining), t_id, a_key, u_id, public_only=public_only)
            for row in rows:
                if row.config_key in remaining:
                    val = self._decrypt_if_needed(row)
                    result[row.config_key] = val
                    remaining.discard(row.config_key)

        await self._set_cached_merged(keys, tenant_id, app_key, user_id, public_only, result)
        logger.debug(
            "config_cache_miss",
            keys=keys,
            tenant_id=tenant_id,
            app_key=app_key,
            user_id=user_id,
            public_only=public_only,
            missing=list(remaining),
        )
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
        public_only: bool = False,
    ) -> str | None:
        """获取单个配置值，指定具体层级"""
        rows = await self._query_scope(scope, [config_key], tenant_id, app_key, user_id, public_only=public_only)
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
        category: str | None = None,
        config_type: str = "input",
        default_value: str | None = None,
        options: list | dict | None = None,
        required: bool = False,
        regex: str | None = None,
        min_value: int | None = None,
        max_value: int | None = None,
        sort: int = 0,
        status: int = 1,
        label: str | None = None,
        description: str | None = None,
        is_public: bool = False,
        changed_by: int | None = None,
        keep_encrypted_value: bool = False,
    ) -> SysConfig:
        """
        设置配置值（不存在则创建，已存在则更新）。
        自动写入变更历史（异步，不影响主流程）。
        """
        # 查询已有记录
        stmt = self._build_scope_stmt(scope, [config_key], tenant_id, app_key, user_id)
        result = await self.db.execute(stmt)
        existing: SysConfig | None = result.scalar_one_or_none()

        old_value = "******" if existing and existing.is_encrypted else (self._decrypt_if_needed(existing) if existing else None)
        self._validate_config_value(
            config_val,
            val_type=val_type,
            required=required,
            regex=regex,
            min_value=min_value,
            max_value=max_value,
            skip_empty=bool(existing and keep_encrypted_value),
        )

        # 加密处理
        store_val = config_val
        if existing and keep_encrypted_value:
            store_val = existing.config_val or ""
        elif is_encrypted:
            from app.core.security import encrypt_value
            store_val = encrypt_value(config_val)

        if existing:
            existing.config_val = store_val
            existing.val_type = val_type
            existing.is_encrypted = is_encrypted
            existing.category = category
            existing.config_type = config_type
            existing.default_value = default_value
            existing.options = options
            existing.required = required
            existing.regex = regex
            existing.min_value = min_value
            existing.max_value = max_value
            existing.sort = sort
            existing.status = status
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
                category=category,
                config_type=config_type,
                default_value=default_value,
                options=options,
                required=required,
                regex=regex,
                min_value=min_value,
                max_value=max_value,
                sort=sort,
                status=status,
                label=label,
                description=description,
                is_public=is_public,
            )
            self.db.add(obj)
            await self.db.flush()

        # 失效 Redis 缓存
        await self._invalidate_cache(scope, tenant_id, app_key, user_id)

        # 如果是多租户开关变更，失效多租户缓存
        if config_key == "multi_tenant.enabled":
            from app.core.multi_tenant import invalidate_multi_tenant_cache
            await invalidate_multi_tenant_cache()

        # 异步写入变更历史（fire-and-forget）
        await self._write_history(
            config_key=config_key,
            scope_type=scope,
            scope_id=tenant_id or user_id,
            old_value=old_value,
            new_value="******" if is_encrypted or keep_encrypted_value else config_val,
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
        changed_by: int | None = None,
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
        await self._write_history(
            config_key=config_key,
            scope_type=scope,
            scope_id=tenant_id or user_id,
            old_value="******" if obj.is_encrypted else self._decrypt_if_needed(obj),
            new_value=None,
            changed_by=changed_by,
        )
        return True

    async def export_items(
        self,
        *,
        scope: str = "global",
        tenant_id: int | None = None,
        app_key: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        is_public: bool | None = None,
        is_encrypted: bool | None = None,
        status: int | None = None,
    ) -> list[dict[str, Any]]:
        """导出配置项。加密配置不导出明文，避免敏感信息泄露。"""
        rows = await self.list_by_scope(
            scope=scope,
            tenant_id=tenant_id,
            app_key=app_key,
            category=category,
            keyword=keyword,
            is_public=is_public,
            is_encrypted=is_encrypted,
            status=status,
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            data = self.to_output(row)
            if row.is_encrypted:
                data["config_val"] = None
                data["display_val"] = "******" if row.config_val else ""
            items.append(data)
        return items

    async def import_items(
        self,
        items: list[dict[str, Any]],
        *,
        overwrite: bool,
        tenant_id: int | None,
        changed_by: int | None,
    ) -> dict[str, Any]:
        """批量导入配置项。返回创建、更新、跳过和错误明细。"""
        result = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

        for index, item in enumerate(items, start=1):
            config_key = str(item.get("config_key") or "").strip()
            scope = str(item.get("scope") or "global")
            if not config_key:
                result["errors"].append(f"第 {index} 条缺少配置键")
                result["skipped"] += 1
                continue

            target_tenant_id = None if scope == "global" else tenant_id
            app_key = item.get("app_key")
            user_id = item.get("user_id")
            stmt = self._build_scope_stmt(scope, [config_key], target_tenant_id, app_key, user_id)
            existing = (await self.db.execute(stmt)).scalar_one_or_none()
            if existing and not overwrite:
                result["skipped"] += 1
                continue

            is_encrypted = bool(item.get("is_encrypted", False))
            config_val = item.get("config_val")
            if is_encrypted and not config_val and not existing:
                result["errors"].append(f"第 {index} 条「{config_key}」为加密配置且没有明文值，已跳过")
                result["skipped"] += 1
                continue

            try:
                await self.set(
                    config_key=config_key,
                    config_val=str(config_val or ""),
                    scope=scope,
                    tenant_id=target_tenant_id,
                    app_key=app_key,
                    user_id=user_id,
                    val_type=str(item.get("val_type") or "string"),
                    is_encrypted=is_encrypted,
                    category=item.get("category"),
                    config_type=str(item.get("config_type") or "input"),
                    default_value=item.get("default_value"),
                    options=item.get("options"),
                    required=bool(item.get("required", False)),
                    regex=item.get("regex"),
                    min_value=item.get("min_value"),
                    max_value=item.get("max_value"),
                    sort=int(item.get("sort") or 0),
                    status=int(item.get("status") if item.get("status") is not None else 1),
                    label=item.get("label"),
                    description=item.get("description"),
                    is_public=bool(item.get("is_public", False)),
                    changed_by=changed_by,
                    keep_encrypted_value=bool(existing and is_encrypted and not config_val),
                )
                result["updated" if existing else "created"] += 1
            except Exception as exc:
                result["errors"].append(f"第 {index} 条「{config_key}」导入失败：{exc}")
                result["skipped"] += 1

        return result

    async def list_by_scope(
        self,
        scope: str,
        *,
        tenant_id: int | None = None,
        app_key: str | None = None,
        user_id: int | None = None,
        category: str | None = None,
        keyword: str | None = None,
        is_public: bool | None = None,
        is_encrypted: bool | None = None,
        status: int | None = None,
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
        if category:
            stmt = stmt.where(SysConfig.category == category)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                SysConfig.config_key.ilike(like)
                | SysConfig.label.ilike(like)
                | SysConfig.description.ilike(like)
            )
        if is_public is not None:
            stmt = stmt.where(SysConfig.is_public == is_public)
        if is_encrypted is not None:
            stmt = stmt.where(SysConfig.is_encrypted == is_encrypted)
        if status is not None:
            stmt = stmt.where(SysConfig.status == status)
        stmt = stmt.order_by(asc(SysConfig.sort), asc(SysConfig.id))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def to_output(row: SysConfig) -> dict[str, Any]:
        """输出给管理端，敏感配置只展示脱敏值。"""
        data = {
            "id": row.id,
            "scope": row.scope,
            "config_key": row.config_key,
            "config_val": None if row.is_encrypted else (row.config_val or ""),
            "display_val": "******" if row.is_encrypted and row.config_val else (row.config_val or ""),
            "val_type": row.val_type,
            "is_encrypted": row.is_encrypted,
            "category": row.category,
            "config_type": row.config_type,
            "default_value": row.default_value,
            "options": row.options,
            "required": row.required,
            "regex": row.regex,
            "min_value": row.min_value,
            "max_value": row.max_value,
            "sort": row.sort,
            "status": row.status,
            "label": row.label,
            "description": row.description,
            "is_public": row.is_public,
            "app_key": row.app_key,
            "user_id": row.user_id,
            "tenant_id": row.tenant_id,
        }
        return data

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
        public_only: bool = False,
    ) -> list[SysConfig]:
        stmt = self._build_scope_stmt(scope, keys, tenant_id, app_key, user_id)
        stmt = stmt.where(SysConfig.status == 1)
        if public_only:
            stmt = stmt.where(SysConfig.is_public == True).where(SysConfig.is_encrypted == False)
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

    def _validate_config_value(
        self,
        value: str,
        *,
        val_type: str,
        required: bool,
        regex: str | None,
        min_value: int | None,
        max_value: int | None,
        skip_empty: bool = False,
    ) -> None:
        if skip_empty and value == "":
            return
        if required and value == "":
            raise ValidationException("配置值不能为空")
        if value == "":
            return
        if val_type == "json":
            try:
                json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValidationException(f"JSON 格式不正确：{exc.msg}") from exc
        if val_type in {"int", "number"}:
            try:
                num = int(value) if val_type == "int" else float(value)
            except ValueError as exc:
                raise ValidationException("配置值必须是数字") from exc
            if min_value is not None and num < min_value:
                raise ValidationException(f"配置值不能小于 {min_value}")
            if max_value is not None and num > max_value:
                raise ValidationException(f"配置值不能大于 {max_value}")
        if val_type == "bool" and value.lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            raise ValidationException("布尔配置值必须是 true/false")
        if regex and not re.fullmatch(regex, value):
            raise ValidationException("配置值不符合正则校验规则")

    @staticmethod
    def _decrypt_if_needed(row: SysConfig | None) -> str:
        if row is None:
            return ""
        if row.is_encrypted and row.config_val:
            try:
                from app.core.security import decrypt_value
                return decrypt_value(row.config_val)
            except Exception as e:
                logger.warning("config_decrypt_failed", key=row.config_key, error=str(e))
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
            count = await self.clear_merged_cache()
            logger.debug(
                "config_cache_invalidated",
                scope=scope,
                tenant_id=tenant_id,
                app_key=app_key,
                user_id=user_id,
                count=count,
            )
        except Exception as e:
            logger.warning("config_cache_invalidate_failed", error=str(e))

    async def clear_merged_cache(self) -> int:
        """清理合并配置缓存，返回删除的 key 数量。"""
        redis = await get_redis_client()
        keys: list[str] = []
        async for key in redis.scan_iter("config:merged:*", count=100):
            keys.append(key)
        if keys:
            await redis.delete(*keys)
        return len(keys)

    async def _get_cached_merged(
        self,
        keys: list[str],
        tenant_id: int | None,
        app_key: str | None,
        user_id: int | None,
        public_only: bool,
    ) -> dict[str, str] | None:
        try:
            redis = await get_redis_client()
            cache_key = _merged_cache_key(keys, tenant_id, app_key, user_id, public_only)
            raw = await redis.get(cache_key)
            if not raw:
                return None
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception as e:
            logger.debug("config_cache_read_failed", error=str(e))
            return None

    async def _set_cached_merged(
        self,
        keys: list[str],
        tenant_id: int | None,
        app_key: str | None,
        user_id: int | None,
        public_only: bool,
        value: dict[str, str],
    ) -> None:
        try:
            redis = await get_redis_client()
            cache_key = _merged_cache_key(keys, tenant_id, app_key, user_id, public_only)
            await redis.setex(cache_key, _CACHE_TTL, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.debug("config_cache_write_failed", error=str(e))

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
