"""钉钉适配器。"""
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


class DingTalkAdapter(WebhookAdapter):
    provider = "dingtalk"
    name = "钉钉"
    capabilities = ["bot_message", "oauth", "contact_sync", "event_callback"]
    required_secret_fields = []
    optional_secret_fields = ["webhook_url", "app_key", "app_secret", "signing_secret"]
    config_fields = ["agent_id"]

    async def _test_app_credentials(self, ctx: AdapterContext) -> AdapterResult:
        app_key = ctx.secret_config.get("app_key")
        app_secret = ctx.secret_config.get("app_secret")
        if not app_key or not app_secret:
            return AdapterResult(success=False, message="缺少 app_key 或 app_secret")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://oapi.dingtalk.com/gettoken",
                    params={"appkey": app_key, "appsecret": app_secret},
                )
                data = self._safe_json(resp)
        except httpx.HTTPError as exc:
            return AdapterResult(success=False, message=f"钉钉凭证测试失败: {exc}")

        if resp.status_code < 400 and data.get("errcode") == 0:
            return AdapterResult(success=True, message="钉钉应用凭证有效")
        return AdapterResult(success=False, message=data.get("errmsg") or "钉钉应用凭证无效", details=data)

    async def fetch_contacts(self, ctx: AdapterContext) -> ContactSyncData:
        access_token = await self._get_access_token(ctx)
        departments: list[ContactDepartment] = []
        users_by_id: dict[str, ContactUser] = {}

        async with httpx.AsyncClient(timeout=20) as client:
            dept_ids = ["1", *await self._collect_department_ids(client, access_token, 1)]
            dept_ids = list(dict.fromkeys(dept_ids))
            for dept_id in dept_ids:
                dept_resp = await client.post(
                    "https://oapi.dingtalk.com/topapi/v2/department/get",
                    params={"access_token": access_token},
                    json={"dept_id": int(dept_id), "language": "zh_CN"},
                )
                dept_data = self._safe_json(dept_resp)
                self._ensure_success(dept_data, "获取钉钉部门详情失败")
                result = dept_data.get("result") or {}
                parent_id = result.get("parent_id")
                departments.append(
                    ContactDepartment(
                        external_id=str(result.get("dept_id") or dept_id),
                        name=result.get("name") or "未命名部门",
                        parent_external_id=str(parent_id) if parent_id not in (None, 0, 1, "0", "1") else None,
                        sort=int(result.get("order") or 0),
                        raw=result,
                    )
                )

                user_ids = await self._list_department_user_ids(client, access_token, int(dept_id))
                for user_id in user_ids:
                    user_resp = await client.post(
                        "https://oapi.dingtalk.com/topapi/v2/user/get",
                        params={"access_token": access_token},
                        json={"userid": user_id, "language": "zh_CN"},
                    )
                    user_data = self._safe_json(user_resp)
                    self._ensure_success(user_data, f"获取钉钉用户「{user_id}」详情失败")
                    item = user_data.get("result") or {}
                    external_id = item.get("userid") or user_id
                    dept_id_list = [str(item_id) for item_id in item.get("dept_id_list", []) if item_id is not None]
                    existing = users_by_id.get(str(external_id))
                    merged_dept_ids = sorted(set((existing.department_external_ids if existing else []) + dept_id_list))
                    users_by_id[str(external_id)] = ContactUser(
                        external_id=str(external_id),
                        name=item.get("name") or str(external_id),
                        nickname=item.get("nickname") or None,
                        email=item.get("email") or None,
                        phone=item.get("mobile") or None,
                        avatar=item.get("avatar") or None,
                        department_external_ids=merged_dept_ids,
                        active=not bool(item.get("exclusive_account")),
                        raw=item,
                    )

        return ContactSyncData(departments=departments, users=list(users_by_id.values()))

    async def _get_access_token(self, ctx: AdapterContext) -> str:
        app_key = ctx.secret_config.get("app_key")
        app_secret = ctx.secret_config.get("app_secret")
        if not app_key or not app_secret:
            raise ValueError("缺少钉钉 app_key 或 app_secret")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://oapi.dingtalk.com/gettoken",
                params={"appkey": app_key, "appsecret": app_secret},
            )
            data = self._safe_json(resp)
        self._ensure_success(data, "获取钉钉 access_token 失败")
        return str(data["access_token"])

    async def _collect_department_ids(self, client: httpx.AsyncClient, access_token: str, dept_id: int) -> list[str]:
        resp = await client.post(
            "https://oapi.dingtalk.com/topapi/v2/department/listsubid",
            params={"access_token": access_token},
            json={"dept_id": dept_id},
        )
        data = self._safe_json(resp)
        self._ensure_success(data, "获取钉钉子部门失败")
        child_ids = [str(item) for item in (data.get("result") or {}).get("dept_id_list", [])]
        all_ids = child_ids.copy()
        for child_id in child_ids:
            all_ids.extend(await self._collect_department_ids(client, access_token, int(child_id)))
        return all_ids

    async def _list_department_user_ids(self, client: httpx.AsyncClient, access_token: str, dept_id: int) -> list[str]:
        resp = await client.post(
            "https://oapi.dingtalk.com/topapi/user/listid",
            params={"access_token": access_token},
            json={"dept_id": dept_id},
        )
        data = self._safe_json(resp)
        self._ensure_success(data, "获取钉钉部门用户失败")
        return [str(item) for item in (data.get("result") or {}).get("userid_list", [])]

    @staticmethod
    def _ensure_success(data: dict[str, Any], default_message: str) -> None:
        if data.get("errcode") not in (0, None):
            raise ValueError(data.get("errmsg") or default_message)

    def _build_webhook_payload(self, *, message_type: str, title: str | None, content: str) -> dict[str, Any]:
        if message_type == "markdown":
            return {
                "msgtype": "markdown",
                "markdown": {"title": title or "通知", "text": f"### {title}\n{content}" if title else content},
            }
        return {"msgtype": "text", "text": {"content": f"{title}\n{content}" if title else content}}
