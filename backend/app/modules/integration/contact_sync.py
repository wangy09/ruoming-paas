"""
通讯录同步服务。
第一版支持企业微信、钉钉的手动全量同步。
"""
import hashlib
import re
import secrets

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.core.security import hash_password
from app.modules.integration.adapters.base import ContactDepartment, ContactUser
from app.modules.integration.models import SysExternalIdentity, SysIntegrationConnection
from app.modules.integration.schemas import ContactSyncRequest, ContactSyncResult
from app.modules.integration.service import IntegrationService
from app.modules.system.models import SysDept
from app.modules.user.models import SysUser


class ContactSyncService:
    """外部通讯录同步到本地组织与账号。"""

    def __init__(self, db: AsyncSession, current_user: SysUser) -> None:
        self.db = db
        self.current_user = current_user
        self.tenant_id = None if current_user.is_superplatform else current_user.tenant_id
        self.integration_service = IntegrationService(db, current_user)

    async def sync(self, data: ContactSyncRequest) -> ContactSyncResult:
        conn = await self.integration_service._resolve_connection(data.connection_id, data.provider)
        if "contact_sync" not in (conn.capabilities or []):
            raise ValidationException("当前连接未启用通讯录同步能力")

        adapter = self.integration_service._get_adapter(conn.provider)
        ctx = self.integration_service._build_context(conn)
        self.integration_service.validate_capability_secret_fields(conn.provider, conn.capabilities or [], ctx.secret_config)
        try:
            sync_data = await adapter.fetch_contacts(ctx)
        except NotImplementedError as exc:
            raise ValidationException("当前平台暂不支持通讯录同步") from exc
        except Exception as exc:
            raise ValidationException(f"拉取外部通讯录失败: {exc}") from exc

        result = ContactSyncResult(provider=conn.provider, connection_id=conn.id)
        dept_map: dict[str, SysDept] = {}
        if data.sync_departments:
            dept_map = await self._sync_departments(conn, sync_data.departments, result)
        else:
            dept_map = await self._load_department_map(conn)

        if data.sync_users:
            await self._sync_users(conn, sync_data.users, dept_map, data, result)

        await self.db.flush()
        return result

    async def _sync_departments(
        self,
        conn: SysIntegrationConnection,
        departments: list[ContactDepartment],
        result: ContactSyncResult,
    ) -> dict[str, SysDept]:
        dept_map = await self._load_department_map(conn)
        pending = {dept.external_id: dept for dept in departments}

        while pending:
            progressed = False
            for external_id, item in list(pending.items()):
                if item.parent_external_id and item.parent_external_id not in dept_map:
                    if item.parent_external_id in pending:
                        continue
                parent = dept_map.get(item.parent_external_id) if item.parent_external_id else None
                dept = dept_map.get(external_id)
                if not dept:
                    dept = SysDept(
                        name=item.name,
                        parent_id=parent.id if parent else 0,
                        ancestors=self._build_ancestors(parent),
                        level=(parent.level + 1) if parent else 1,
                        sort=item.sort,
                        status=1,
                        tenant_id=self.tenant_id,
                        remark=f"由{conn.name}同步",
                    )
                    self.db.add(dept)
                    await self.db.flush()
                    await self._upsert_identity(conn, "dept", external_id, dept.id, item.raw)
                    dept_map[external_id] = dept
                    result.departments_created += 1
                else:
                    dept.name = item.name
                    dept.parent_id = parent.id if parent else 0
                    dept.ancestors = self._build_ancestors(parent)
                    dept.level = (parent.level + 1) if parent else 1
                    dept.sort = item.sort
                    dept.status = 1
                    dept.is_deleted = False
                    await self._upsert_identity(conn, "dept", external_id, dept.id, item.raw)
                    result.departments_updated += 1
                pending.pop(external_id)
                progressed = True

            if not progressed:
                for external_id, item in list(pending.items()):
                    result.errors.append(f"部门「{item.name}」父级不存在，已按根部门同步")
                    item = ContactDepartment(
                        external_id=item.external_id,
                        name=item.name,
                        parent_external_id=None,
                        sort=item.sort,
                        raw=item.raw,
                    )
                    pending[external_id] = item

        return dept_map

    async def _sync_users(
        self,
        conn: SysIntegrationConnection,
        users: list[ContactUser],
        dept_map: dict[str, SysDept],
        request: ContactSyncRequest,
        result: ContactSyncResult,
    ) -> None:
        synced_user_ids: set[int] = set()
        for item in users:
            dept_id = self._pick_department_id(item, dept_map)
            user = await self._find_user(conn, item)
            if not user:
                username = await self._generate_username(conn.provider, item)
                user = SysUser(
                    username=username,
                    password=hash_password(secrets.token_urlsafe(24)),
                    nickname=username,
                    email=await self._safe_email(item.email),
                    phone=item.phone or None,
                    avatar=item.avatar if request.sync_avatar else None,
                    status=1 if item.active else 0,
                    dept_id=dept_id,
                    tenant_id=self.tenant_id,
                    remark=f"由{conn.name}同步创建",
                )
                self.db.add(user)
                await self.db.flush()
                result.users_created += 1
            else:
                user.nickname = self._pick_nickname(item) or user.nickname
                safe_email = await self._safe_email(item.email, user.id)
                if safe_email or item.email is None:
                    user.email = safe_email
                user.phone = item.phone or user.phone
                if request.sync_avatar and item.avatar:
                    user.avatar = item.avatar
                user.status = 1 if item.active else 0
                if dept_id is not None:
                    user.dept_id = dept_id
                user.is_deleted = False
                result.users_updated += 1

            await self._upsert_identity(conn, "user", item.external_id, user.id, item.raw)
            synced_user_ids.add(user.id)

        if request.disable_missing_users:
            await self._disable_missing_users(conn, synced_user_ids, result)

    async def _load_department_map(self, conn: SysIntegrationConnection) -> dict[str, SysDept]:
        rows = await self.db.execute(
            select(SysExternalIdentity, SysDept)
            .join(SysDept, SysDept.id == SysExternalIdentity.local_id)
            .where(
                SysExternalIdentity.connection_id == conn.id,
                SysExternalIdentity.identity_type == "dept",
                SysExternalIdentity.is_deleted == False,  # noqa: E712
                SysDept.is_deleted == False,  # noqa: E712
            )
        )
        return {identity.external_id: dept for identity, dept in rows.all()}

    async def _find_user(self, conn: SysIntegrationConnection, item: ContactUser) -> SysUser | None:
        external_ids = {item.external_id}
        for key in ("open_id", "union_id", "user_id"):
            value = item.raw.get(key) if isinstance(item.raw, dict) else None
            if value:
                external_ids.add(str(value))

        mapped = await self.db.execute(
            select(SysUser)
            .join(SysExternalIdentity, SysExternalIdentity.local_id == SysUser.id)
            .where(
                SysExternalIdentity.connection_id == conn.id,
                SysExternalIdentity.identity_type == "user",
                SysExternalIdentity.external_id.in_(external_ids),
                SysExternalIdentity.is_deleted == False,  # noqa: E712
                SysUser.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
        user = mapped.scalar_one_or_none()
        if user:
            return user

        conditions = [SysUser.is_deleted == False]  # noqa: E712
        if self.tenant_id is None:
            conditions.append(SysUser.tenant_id.is_(None))
        else:
            conditions.append(SysUser.tenant_id == self.tenant_id)
        match_fields = []
        if item.phone:
            match_fields.append(SysUser.phone == item.phone)
        if item.email:
            match_fields.append(SysUser.email == item.email)
        if not match_fields:
            return None
        conditions.append(or_(*match_fields))
        result = await self.db.execute(select(SysUser).where(*conditions).limit(1))
        return result.scalar_one_or_none()

    async def _upsert_identity(
        self,
        conn: SysIntegrationConnection,
        identity_type: str,
        external_id: str,
        local_id: int,
        raw_data: dict,
    ) -> None:
        identity = await self.db.scalar(
            select(SysExternalIdentity).where(
                SysExternalIdentity.connection_id == conn.id,
                SysExternalIdentity.identity_type == identity_type,
                SysExternalIdentity.external_id == external_id,
                SysExternalIdentity.is_deleted == False,  # noqa: E712
            )
        )
        if not identity:
            identity = SysExternalIdentity(
                connection_id=conn.id,
                provider=conn.provider,
                identity_type=identity_type,
                external_id=external_id,
                local_id=local_id,
                raw_data=raw_data,
                tenant_id=self.tenant_id,
            )
            self.db.add(identity)
            return
        identity.local_id = local_id
        identity.raw_data = raw_data
        identity.is_deleted = False

    async def _disable_missing_users(
        self,
        conn: SysIntegrationConnection,
        synced_user_ids: set[int],
        result: ContactSyncResult,
    ) -> None:
        rows = await self.db.execute(
            select(SysUser)
            .join(SysExternalIdentity, SysExternalIdentity.local_id == SysUser.id)
            .where(
                SysExternalIdentity.connection_id == conn.id,
                SysExternalIdentity.identity_type == "user",
                SysExternalIdentity.is_deleted == False,  # noqa: E712
                SysUser.is_deleted == False,  # noqa: E712
            )
        )
        for user in rows.scalars().all():
            if user.id in synced_user_ids:
                continue
            if user.status != 0:
                user.status = 0
                result.users_disabled += 1

    def _pick_department_id(self, item: ContactUser, dept_map: dict[str, SysDept]) -> int | None:
        for external_id in item.department_external_ids:
            dept = dept_map.get(external_id)
            if dept:
                return dept.id
        return None

    @staticmethod
    def _build_ancestors(parent: SysDept | None) -> str:
        if not parent:
            return "0"
        return f"{parent.ancestors},{parent.id}" if parent.ancestors else f"0,{parent.id}"

    @staticmethod
    def _pick_nickname(item: ContactUser) -> str | None:
        """外部通讯录同步显示名，优先使用 name，避免 nickname 覆盖真实姓名。"""
        return (item.name or "").strip() or (item.nickname or "").strip() or None

    async def _generate_username(self, provider: str, item: ContactUser) -> str:
        """按邮箱前缀、手机号、姓名、平台外部 ID 的顺序生成唯一用户名。"""
        candidates = [
            (item.email or "").split("@", 1)[0],
            item.phone,
            item.name,
            self._provider_external_username(provider, item.external_id),
        ]
        for candidate in candidates:
            base = self._normalize_username(candidate)
            if base:
                return await self._ensure_unique_username(base)

        return await self._ensure_unique_username(f"{provider}_{secrets.token_hex(4)}")

    @staticmethod
    def _provider_external_username(provider: str, external_id: str) -> str:
        """使用 provider + 短 external_id 作为最后兜底，外部 ID 不安全时使用短哈希。"""
        normalized_external_id = ContactSyncService._normalize_username(
            external_id,
            max_length=16,
        )
        short_external_id = normalized_external_id or hashlib.sha1(
            external_id.encode("utf-8")
        ).hexdigest()[:8]
        return f"{provider}_{short_external_id}"

    @staticmethod
    def _normalize_username(value: str | None, *, max_length: int = 64) -> str:
        """转换为登录用户名安全字符，仅保留字母、数字、下划线和连字符。"""
        if not value:
            return ""
        normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()).strip("_-")
        normalized = re.sub(r"[_-]{2,}", "_", normalized)
        if len(normalized) < 3:
            return ""
        return normalized[:max_length]

    async def _ensure_unique_username(self, base: str) -> str:
        """确保用户名在 sys_user 全表唯一，包含软删除数据以满足唯一索引约束。"""
        username = base[:64]
        index = 1
        while await self.db.scalar(select(SysUser.id).where(SysUser.username == username)):
            suffix = f"_{index}"
            username = f"{base[:64 - len(suffix)]}{suffix}"
            index += 1
        return username

    async def _safe_email(self, email: str | None, current_user_id: int | None = None) -> str | None:
        if not email:
            return None
        conditions = [
            SysUser.email == email,
            SysUser.is_deleted == False,  # noqa: E712
        ]
        if current_user_id:
            conditions.append(SysUser.id != current_user_id)
        exists = await self.db.scalar(select(SysUser.id).where(*conditions))
        return None if exists else email
