"""
通讯录同步服务。
第一版支持企业微信、钉钉的手动全量同步。
"""
import hashlib
import math
import re
import secrets
from typing import Literal, Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.core.security import hash_password
from app.modules.integration.adapters.base import ContactDepartment, ContactUser
from app.modules.integration.models import SysContactSyncLog, SysExternalIdentity, SysIntegrationConnection
from app.modules.integration.schemas import (
    ContactSyncCheckItem,
    ContactSyncCheckResult,
    ContactSyncPreviewItem,
    ContactSyncPreviewResult,
    ContactSyncRequest,
    ContactSyncResult,
)
from app.modules.integration.service import IntegrationService
from app.modules.system.models import SysDept
from app.modules.user.models import SysUser


class ContactSyncService:
    """外部通讯录同步到本地组织与账号。"""

    MISSING_USER_DISABLE_MIN_RETURN_RATIO = 0.8

    def __init__(self, db: AsyncSession, current_user: SysUser) -> None:
        self.db = db
        self.current_user = current_user
        self.tenant_id = None if current_user.is_superplatform else current_user.tenant_id
        self.integration_service = IntegrationService(db, current_user)

    async def sync(self, data: ContactSyncRequest) -> ContactSyncResult:
        conn, sync_data = await self._fetch_sync_data(data)

        result = ContactSyncResult(provider=conn.provider, connection_id=conn.id)
        if data.disable_missing_users and data.sync_users:
            active_mapped_user_count = await self._count_active_mapped_users(conn)
            is_safe, protection_message = self._check_missing_user_disable_safety(
                fetched_user_count=len(sync_data.users),
                active_mapped_user_count=active_mapped_user_count,
            )
            if not is_safe:
                result.errors.append(protection_message)
                await self._write_sync_log(conn, "sync", data, result)
                return result

        dept_map: dict[str, SysDept] = {}
        if data.sync_departments:
            dept_map = await self._sync_departments(conn, sync_data.departments, result)
        else:
            dept_map = await self._load_department_map(conn)

        if data.sync_users:
            await self._sync_users(conn, sync_data.users, dept_map, data, result)

        await self.db.flush()
        await self._write_sync_log(conn, "sync", data, result)
        return result

    async def preview(self, data: ContactSyncRequest) -> ContactSyncPreviewResult:
        conn, sync_data = await self._fetch_sync_data(data)
        result = ContactSyncPreviewResult(provider=conn.provider, connection_id=conn.id)

        details: list[ContactSyncPreviewItem] = []
        dept_map = await self._load_department_map(conn)
        if data.sync_departments:
            for item in sync_data.departments:
                dept = dept_map.get(item.external_id)
                if dept:
                    result.departments_updated += 1
                    self._append_preview_detail(
                        details,
                        action="update",
                        target_type="department",
                        external_id=item.external_id,
                        local_id=dept.id,
                        name=item.name,
                    )
                else:
                    result.departments_created += 1
                    self._append_preview_detail(
                        details,
                        action="create",
                        target_type="department",
                        external_id=item.external_id,
                        name=item.name,
                    )
        elif data.sync_users:
            dept_map = await self._load_department_map(conn)

        synced_user_ids: set[int] = set()
        if data.sync_users:
            for item in sync_data.users:
                user = await self._find_user(conn, item)
                display_name = self._pick_nickname(item) or item.external_id
                if user:
                    synced_user_ids.add(user.id)
                    result.users_updated += 1
                    self._append_preview_detail(
                        details,
                        action="update",
                        target_type="user",
                        external_id=item.external_id,
                        local_id=user.id,
                        name=display_name,
                    )
                else:
                    result.users_created += 1
                    self._append_preview_detail(
                        details,
                        action="create",
                        target_type="user",
                        external_id=item.external_id,
                        name=display_name,
                    )

            if data.disable_missing_users:
                result.users_disabled = await self._count_missing_users(conn, synced_user_ids, details)

        result.details = details
        await self._write_sync_log(conn, "preview", data, result)
        return result

    async def check(self, data: ContactSyncRequest) -> ContactSyncCheckResult:
        """检查通讯录同步配置和外部数据可用性，不写入用户或部门。"""
        result = ContactSyncCheckResult(
            provider=data.provider,
            status="failed",
            summary="通讯录同步自检失败",
        )
        checks = result.checks

        try:
            conn = await self.integration_service._resolve_connection(data.connection_id, data.provider)
        except Exception as exc:
            self._append_check(
                checks,
                "connection",
                "连接状态",
                "failed",
                f"连接不可用：{exc}",
            )
            result.status = "failed"
            result.summary = "集成连接不可用，请先检查连接是否启用或默认连接是否存在"
            return result

        result.provider = conn.provider
        result.connection_id = conn.id
        self._append_check(
            checks,
            "connection",
            "连接状态",
            "success",
            f"已选择连接「{conn.name}」",
            connection_id=conn.id,
        )

        if "contact_sync" not in (conn.capabilities or []):
            self._append_check(
                checks,
                "capability",
                "通讯录能力",
                "failed",
                "当前连接未启用通讯录同步能力",
            )
            result.status = "failed"
            result.summary = "当前连接未启用通讯录同步能力"
            return result
        self._append_check(checks, "capability", "通讯录能力", "success", "已启用通讯录同步能力")

        try:
            adapter = self.integration_service._get_adapter(conn.provider)
            ctx = self.integration_service._build_context(conn)
            self.integration_service.validate_capability_secret_fields(
                conn.provider,
                conn.capabilities or [],
                ctx.secret_config,
            )
        except Exception as exc:
            self._append_check(checks, "credentials", "凭证配置", "failed", f"凭证不可用：{exc}")
            result.status = "failed"
            result.summary = "通讯录同步凭证不完整或无法解密"
            return result
        self._append_check(checks, "credentials", "凭证配置", "success", "通讯录同步所需凭证已保存")

        try:
            sync_data = await adapter.fetch_contacts(ctx)
        except NotImplementedError:
            self._append_check(checks, "fetch_contacts", "拉取通讯录", "failed", "当前平台暂不支持通讯录同步")
            result.status = "failed"
            result.summary = "当前平台暂不支持通讯录同步"
            return result
        except Exception as exc:
            self._append_check(checks, "fetch_contacts", "拉取通讯录", "failed", f"拉取外部通讯录失败：{exc}")
            result.status = "failed"
            result.summary = "拉取外部通讯录失败，请检查平台权限和通讯录授权范围"
            return result

        result.departments_count = len(sync_data.departments)
        result.users_count = len(sync_data.users)
        result.avatar_users_count = len([item for item in sync_data.users if item.avatar])
        self._append_check(
            checks,
            "fetch_contacts",
            "拉取通讯录",
            "success",
            f"已拉取 {result.departments_count} 个部门、{result.users_count} 个用户",
            departments_count=result.departments_count,
            users_count=result.users_count,
        )

        if data.sync_departments:
            if result.departments_count:
                self._append_check(checks, "departments", "部门数据", "success", "外部平台返回了可同步部门")
            else:
                self._append_check(
                    checks,
                    "departments",
                    "部门数据",
                    "warning",
                    "外部平台未返回可同步部门，可能用户都在根部门，或应用通讯录权限范围未包含部门信息",
                )
        if data.sync_users:
            if result.users_count:
                self._append_check(checks, "users", "用户数据", "success", "外部平台返回了可同步用户")
            else:
                self._append_check(checks, "users", "用户数据", "warning", "外部平台未返回可同步用户")

        if data.sync_avatar and data.sync_users:
            if result.users_count == 0:
                self._append_check(checks, "avatar", "头像数据", "warning", "没有可同步用户，无法检查头像数据")
            elif result.avatar_users_count == 0:
                self._append_check(checks, "avatar", "头像数据", "warning", "外部用户数据中未返回头像信息")
            else:
                self._append_check(
                    checks,
                    "avatar",
                    "头像数据",
                    "success",
                    f"{result.avatar_users_count} 个用户包含头像信息",
                )

        self._append_check(
            checks,
            "field_strategy",
            "字段策略",
            "success",
            "已应用当前字段映射和覆盖策略",
            username_strategy=data.username_strategy,
            nickname_strategy=data.nickname_strategy,
            email_update_mode=data.email_update_mode,
            phone_update_mode=data.phone_update_mode,
            department_update_mode=data.department_update_mode,
        )

        if data.disable_missing_users and data.sync_users:
            synced_user_ids: set[int] = set()
            for item in sync_data.users:
                user = await self._find_user(conn, item)
                if user:
                    synced_user_ids.add(user.id)
            result.missing_users_count = await self._count_missing_users(conn, synced_user_ids, [])
            active_mapped_user_count = await self._count_active_mapped_users(conn)
            is_safe, protection_message = self._check_missing_user_disable_safety(
                fetched_user_count=result.users_count,
                active_mapped_user_count=active_mapped_user_count,
            )
            if not is_safe:
                self._append_check(
                    checks,
                    "missing_user_protection",
                    "禁用保护",
                    "failed",
                    protection_message,
                    fetched_user_count=result.users_count,
                    active_mapped_user_count=active_mapped_user_count,
                    min_return_ratio=self.MISSING_USER_DISABLE_MIN_RETURN_RATIO,
                )
            self._append_check(
                checks,
                "missing_users",
                "缺失用户策略",
                "warning" if result.missing_users_count else "success",
                f"开启自动禁用后，本次预计会禁用 {result.missing_users_count} 个缺失用户",
                missing_users_count=result.missing_users_count,
            )
        else:
            self._append_check(checks, "missing_users", "缺失用户策略", "success", "缺失用户将保持不变")

        result.status = self._resolve_check_status(checks)
        if result.status == "success":
            result.summary = "自检通过，可以执行同步"
        elif result.status == "warning":
            result.summary = "自检完成，但存在需要关注的提示"
        else:
            result.summary = "自检失败，请先修复失败项"
        return result

    async def _fetch_sync_data(self, data: ContactSyncRequest):
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
        return conn, sync_data

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
                username = await self._generate_username(conn.provider, item, request.username_strategy)
                user = SysUser(
                    username=username,
                    password=hash_password(secrets.token_urlsafe(24)),
                    nickname=self._pick_nickname(item, request.nickname_strategy, username) or username,
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
                user.nickname = self._pick_nickname(item, request.nickname_strategy, user.username) or user.nickname
                if self._should_update_field(request.email_update_mode, user.email, item.email):
                    safe_email = await self._safe_email(item.email, user.id)
                    if safe_email:
                        user.email = safe_email
                if self._should_update_field(request.phone_update_mode, user.phone, item.phone):
                    user.phone = item.phone
                if request.sync_avatar and item.avatar:
                    user.avatar = item.avatar
                user.status = 1 if item.active else 0
                if self._should_update_field(request.department_update_mode, user.dept_id, dept_id):
                    user.dept_id = dept_id
                user.is_deleted = False
                result.users_updated += 1

            await self._upsert_identity(conn, "user", item.external_id, user.id, item.raw)
            synced_user_ids.add(user.id)

        if request.disable_missing_users:
            await self._disable_missing_users(conn, len(users), synced_user_ids, result)

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
        fetched_user_count: int,
        synced_user_ids: set[int],
        result: ContactSyncResult,
    ) -> None:
        active_mapped_user_count = await self._count_active_mapped_users(conn)
        is_safe, protection_message = self._check_missing_user_disable_safety(
            fetched_user_count=fetched_user_count,
            active_mapped_user_count=active_mapped_user_count,
        )
        if not is_safe:
            result.errors.append(protection_message)
            return

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

    async def _count_active_mapped_users(self, conn: SysIntegrationConnection) -> int:
        rows = await self.db.execute(
            select(SysUser.id)
            .join(SysExternalIdentity, SysExternalIdentity.local_id == SysUser.id)
            .where(
                SysExternalIdentity.connection_id == conn.id,
                SysExternalIdentity.identity_type == "user",
                SysExternalIdentity.is_deleted == False,  # noqa: E712
                SysUser.is_deleted == False,  # noqa: E712
                SysUser.status != 0,
            )
        )
        return len(set(rows.scalars().all()))

    def _check_missing_user_disable_safety(
        self,
        *,
        fetched_user_count: int,
        active_mapped_user_count: int,
    ) -> tuple[bool, str]:
        if active_mapped_user_count <= 0:
            return True, ""
        min_expected_count = math.ceil(active_mapped_user_count * self.MISSING_USER_DISABLE_MIN_RETURN_RATIO)
        if fetched_user_count >= min_expected_count:
            return True, ""
        return (
            False,
            (
                "已阻止自动禁用缺失用户：本次外部通讯录返回用户数 "
                f"{fetched_user_count}，低于当前已映射启用用户数 {active_mapped_user_count} 的 "
                f"{int(self.MISSING_USER_DISABLE_MIN_RETURN_RATIO * 100)}%，请先检查外部平台通讯录权限范围"
            ),
        )

    async def _count_missing_users(
        self,
        conn: SysIntegrationConnection,
        synced_user_ids: set[int],
        details: list[ContactSyncPreviewItem],
    ) -> int:
        rows = await self.db.execute(
            select(SysUser)
            .join(SysExternalIdentity, SysExternalIdentity.local_id == SysUser.id)
            .where(
                SysExternalIdentity.connection_id == conn.id,
                SysExternalIdentity.identity_type == "user",
                SysExternalIdentity.is_deleted == False,  # noqa: E712
                SysUser.is_deleted == False,  # noqa: E712
                SysUser.status != 0,
            )
        )
        count = 0
        for user in rows.scalars().all():
            if user.id in synced_user_ids:
                continue
            count += 1
            self._append_preview_detail(
                details,
                action="disable",
                target_type="user",
                local_id=user.id,
                name=user.nickname or user.username,
                reason="本次外部通讯录未返回该用户",
            )
        return count

    @staticmethod
    def _append_preview_detail(
        details: list[ContactSyncPreviewItem],
        *,
        action: str,
        target_type: str,
        external_id: str | None = None,
        local_id: int | None = None,
        name: str | None = None,
        reason: str | None = None,
    ) -> None:
        if len(details) >= 50:
            return
        details.append(
            ContactSyncPreviewItem(
                action=action,
                target_type=target_type,
                external_id=external_id,
                local_id=local_id,
                name=name,
                reason=reason,
            )
        )

    @staticmethod
    def _append_check(
        checks: list[ContactSyncCheckItem],
        key: str,
        name: str,
        status: Literal["success", "warning", "failed"],
        message: str,
        **details,
    ) -> None:
        checks.append(
            ContactSyncCheckItem(
                key=key,
                name=name,
                status=status,
                message=message,
                details=details,
            )
        )

    @staticmethod
    def _resolve_check_status(checks: list[ContactSyncCheckItem]) -> Literal["success", "warning", "failed"]:
        statuses = {item.status for item in checks}
        if "failed" in statuses:
            return "failed"
        if "warning" in statuses:
            return "warning"
        return "success"

    async def _write_sync_log(
        self,
        conn: SysIntegrationConnection,
        operation: str,
        request: ContactSyncRequest,
        result: ContactSyncResult | ContactSyncPreviewResult,
    ) -> None:
        status = "partial" if result.errors else "success"
        detail_data = {}
        if isinstance(result, ContactSyncPreviewResult):
            detail_data["details"] = [item.model_dump() for item in result.details]
            result_data = result.model_dump(exclude={"details"})
        else:
            result_data = result.model_dump()

        self.db.add(
            SysContactSyncLog(
                connection_id=conn.id,
                provider=conn.provider,
                operation=operation,
                status=status,
                operator_id=self.current_user.id,
                request_data=request.model_dump(),
                result_data=result_data,
                detail_data=detail_data or None,
                tenant_id=self.tenant_id,
            )
        )

    @staticmethod
    def _should_update_field(mode: str, current_value: object, new_value: object) -> bool:
        if new_value is None or new_value == "":
            return False
        if mode == "always":
            return True
        if mode == "if_empty":
            return current_value is None or current_value == ""
        return False

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
    def _pick_nickname(
        item: ContactUser,
        strategy: Sequence[str] | None = None,
        username: str | None = None,
    ) -> str | None:
        """按配置优先级选择外部通讯录显示名。"""
        fields = strategy or ["name", "nickname"]
        values = {
            "name": item.name,
            "nickname": item.nickname,
            "username": username,
        }
        for field in fields:
            value = (values.get(field) or "").strip()
            if value:
                return value
        return None

    async def _generate_username(self, provider: str, item: ContactUser, strategy: Sequence[str] | None = None) -> str:
        """按配置优先级生成唯一用户名。"""
        fields = strategy or ["email_prefix", "phone", "name", "external_id"]
        for field in fields:
            candidate = self._username_candidate(provider, item, field)
            base = self._normalize_username(candidate)
            if base:
                return await self._ensure_unique_username(base)

        return await self._ensure_unique_username(f"{provider}_{secrets.token_hex(4)}")

    @staticmethod
    def _username_candidate(provider: str, item: ContactUser, field: str) -> str | None:
        if field == "email_prefix":
            return (item.email or "").split("@", 1)[0]
        if field == "phone":
            return item.phone
        if field == "name":
            return item.name
        if field == "external_id":
            return ContactSyncService._provider_external_username(provider, item.external_id)
        return None

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
