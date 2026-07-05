"""飞书适配器。"""
from typing import Any

import httpx

from app.modules.integration.adapters.base import (
    AdapterContext,
    AdapterResult,
    ContactDepartment,
    ContactSyncData,
    ContactUser,
)
from app.modules.integration.adapters.webhook import WebhookAdapter


class FeishuAdapter(WebhookAdapter):
    provider = "feishu"
    name = "飞书"
    capabilities = ["bot_message", "oauth", "contact_sync", "event_callback"]
    required_secret_fields = []
    optional_secret_fields = ["webhook_url", "app_id", "app_secret", "encrypt_key", "verification_token"]
    config_fields = ["app_type"]

    async def _test_app_credentials(self, ctx: AdapterContext) -> AdapterResult:
        app_id = ctx.secret_config.get("app_id")
        app_secret = ctx.secret_config.get("app_secret")
        if not app_id or not app_secret:
            return AdapterResult(success=False, message="缺少 app_id 或 app_secret")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": app_id, "app_secret": app_secret},
                )
                data = self._safe_json(resp)
        except httpx.HTTPError as exc:
            return AdapterResult(success=False, message=f"飞书凭证测试失败: {exc}")

        if resp.status_code < 400 and data.get("code") == 0:
            return AdapterResult(success=True, message="飞书应用凭证有效", details={"tenant_key": data.get("tenant_key")})
        return AdapterResult(success=False, message=data.get("msg") or "飞书应用凭证无效", details=data)

    async def fetch_contacts(self, ctx: AdapterContext) -> ContactSyncData:
        tenant_access_token = await self._get_tenant_access_token(ctx)
        headers = {"Authorization": f"Bearer {tenant_access_token}"}
        departments: list[ContactDepartment] = []
        users_by_id: dict[str, ContactUser] = {}

        async with httpx.AsyncClient(timeout=20) as client:
            await self._collect_departments(client, headers, "0", departments)
            for department_id in ["0", *[dept.external_id for dept in departments]]:
                users = await self._list_department_users(client, headers, department_id)
                for item in users:
                    external_id = item.get("open_id") or item.get("union_id") or item.get("user_id")
                    if not external_id:
                        continue
                    detail = await self._get_user_detail(client, headers, str(external_id))
                    if detail:
                        item = {**item, **detail}
                    dept_ids = [str(dept_id) for dept_id in item.get("department_ids", []) if dept_id is not None]
                    existing = users_by_id.get(str(external_id))
                    merged_dept_ids = sorted(set((existing.department_external_ids if existing else []) + dept_ids))
                    is_active = self._is_active_user(item)
                    users_by_id[str(external_id)] = ContactUser(
                        external_id=str(external_id),
                        name=self._extract_display_name(item, existing),
                        nickname=item.get("nickname") or (existing.nickname if existing else None),
                        email=item.get("email") or (existing.email if existing else None),
                        phone=item.get("mobile") or (existing.phone if existing else None),
                        avatar=self._extract_avatar(item) or (existing.avatar if existing else None),
                        department_external_ids=merged_dept_ids,
                        active=is_active if existing is None else existing.active and is_active,
                        raw=item,
                    )

        return ContactSyncData(departments=departments, users=list(users_by_id.values()))

    async def _get_tenant_access_token(self, ctx: AdapterContext) -> str:
        app_id = ctx.secret_config.get("app_id")
        app_secret = ctx.secret_config.get("app_secret")
        if not app_id or not app_secret:
            raise ValueError("缺少飞书 app_id 或 app_secret")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            data = self._safe_json(resp)
        self._ensure_success(data, "获取飞书 tenant_access_token 失败")
        return str(data["tenant_access_token"])

    async def _collect_departments(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        parent_department_id: str,
        departments: list[ContactDepartment],
    ) -> None:
        page_token: str | None = None
        while True:
            params = {
                "department_id_type": "open_department_id",
                "fetch_child": False,
                "page_size": 50,
            }
            if page_token:
                params["page_token"] = page_token
            resp = await client.get(
                f"https://open.feishu.cn/open-apis/contact/v3/departments/{parent_department_id}/children",
                headers=headers,
                params=params,
            )
            data = self._safe_json(resp)
            self._ensure_success(data, "获取飞书部门失败")
            payload = data.get("data") or {}
            items = payload.get("items") or []
            child_ids: list[str] = []
            for item in items:
                external_id = item.get("open_department_id") or item.get("department_id")
                if not external_id:
                    continue
                parent_id = item.get("parent_department_id") or item.get("parent_open_department_id")
                departments.append(
                    ContactDepartment(
                        external_id=str(external_id),
                        name=item.get("name") or item.get("i18n_name", {}).get("zh_cn") or "未命名部门",
                        parent_external_id=str(parent_id) if parent_id not in (None, "0", 0) else None,
                        sort=int(item.get("order") or 0),
                        raw=item,
                    )
                )
                child_ids.append(str(external_id))

            for child_id in child_ids:
                await self._collect_departments(client, headers, child_id, departments)

            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break

    async def _list_department_users(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        department_id: str,
    ) -> list[dict[str, Any]]:
        users: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params = {
                "department_id": department_id,
                "department_id_type": "open_department_id",
                "user_id_type": "open_id",
                "page_size": 50,
            }
            if page_token:
                params["page_token"] = page_token
            resp = await client.get(
                "https://open.feishu.cn/open-apis/contact/v3/users/find_by_department",
                headers=headers,
                params=params,
            )
            data = self._safe_json(resp)
            self._ensure_success(data, "获取飞书部门用户失败")
            payload = data.get("data") or {}
            users.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")
            if not page_token:
                break
        return users

    async def _get_user_detail(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        user_id: str,
    ) -> dict[str, Any]:
        resp = await client.get(
            f"https://open.feishu.cn/open-apis/contact/v3/users/{user_id}",
            headers=headers,
            params={
                "user_id_type": "open_id",
                "department_id_type": "open_department_id",
            },
        )
        data = self._safe_json(resp)
        self._ensure_success(data, "获取飞书用户详情失败")
        payload = data.get("data") or {}
        user = payload.get("user") or payload
        return user if isinstance(user, dict) else {}

    @staticmethod
    def _extract_display_name(item: dict[str, Any], existing: ContactUser | None = None) -> str:
        candidates = FeishuAdapter._display_name_candidates(item, existing)
        chinese_name = next((value for value in candidates if FeishuAdapter._contains_chinese(value)), None)
        if chinese_name:
            return chinese_name
        if candidates:
            return candidates[0]
        external_id = item.get("open_id") or item.get("union_id") or item.get("user_id")
        return str(external_id or "飞书用户")

    @staticmethod
    def _display_name_candidates(item: dict[str, Any], existing: ContactUser | None = None) -> list[str]:
        i18n_name = item.get("i18n_name") or {}
        candidates = [
            i18n_name.get("zh_cn") if isinstance(i18n_name, dict) else None,
            i18n_name.get("zh-CN") if isinstance(i18n_name, dict) else None,
            i18n_name.get("zh_hans") if isinstance(i18n_name, dict) else None,
            item.get("name"),
            item.get("nickname"),
            item.get("en_name"),
            item.get("email"),
            item.get("mobile"),
            existing.name if existing else None,
        ]
        result: list[str] = []
        for value in candidates:
            if isinstance(value, str) and value.strip() and value.strip() not in result:
                result.append(value.strip())
        return result

    @staticmethod
    def _contains_chinese(value: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in value)

    @staticmethod
    def _extract_avatar(item: dict[str, Any]) -> str | None:
        avatar = item.get("avatar") or {}
        if isinstance(avatar, dict):
            return avatar.get("avatar_240") or avatar.get("avatar_72") or avatar.get("avatar_origin")
        return None

    @staticmethod
    def _is_active_user(item: dict[str, Any]) -> bool:
        status = item.get("status") or {}
        if not isinstance(status, dict):
            return True
        if status.get("is_resigned") or status.get("is_frozen"):
            return False
        return status.get("is_activated", True)

    @staticmethod
    def _ensure_success(data: dict[str, Any], default_message: str) -> None:
        if data.get("code") not in (0, None):
            raise ValueError(data.get("msg") or default_message)

    def _build_webhook_payload(self, *, message_type: str, title: str | None, content: str) -> dict[str, Any]:
        if message_type == "markdown":
            text = f"**{title}**\n{content}" if title else content
            return {"msg_type": "interactive", "card": {"elements": [{"tag": "markdown", "content": text}]}}
        return {"msg_type": "text", "content": {"text": f"{title}\n{content}" if title else content}}
