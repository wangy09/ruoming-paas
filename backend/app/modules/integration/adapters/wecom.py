"""企业微信适配器。"""
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


class WeComAdapter(WebhookAdapter):
    provider = "wecom"
    name = "企业微信"
    capabilities = ["bot_message", "oauth", "contact_sync", "event_callback"]
    required_secret_fields = []
    optional_secret_fields = ["webhook_url", "corp_id", "corp_secret", "token", "encoding_aes_key"]
    config_fields = ["agent_id"]

    async def _test_app_credentials(self, ctx: AdapterContext) -> AdapterResult:
        corp_id = ctx.secret_config.get("corp_id")
        corp_secret = ctx.secret_config.get("corp_secret")
        if not corp_id or not corp_secret:
            return AdapterResult(success=False, message="缺少 corp_id 或 corp_secret")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                    params={"corpid": corp_id, "corpsecret": corp_secret},
                )
                data = self._safe_json(resp)
        except httpx.HTTPError as exc:
            return AdapterResult(success=False, message=f"企业微信凭证测试失败: {exc}")

        if resp.status_code < 400 and data.get("errcode") == 0:
            return AdapterResult(success=True, message="企业微信应用凭证有效")
        return AdapterResult(success=False, message=data.get("errmsg") or "企业微信应用凭证无效", details=data)

    async def fetch_contacts(self, ctx: AdapterContext) -> ContactSyncData:
        access_token = await self._get_access_token(ctx)
        async with httpx.AsyncClient(timeout=20) as client:
            dept_resp = await client.get(
                "https://qyapi.weixin.qq.com/cgi-bin/department/list",
                params={"access_token": access_token},
            )
            dept_data = self._safe_json(dept_resp)
            self._ensure_success(dept_data, "获取企业微信部门失败")

            departments = [
                ContactDepartment(
                    external_id=str(item.get("id")),
                    name=item.get("name") or "未命名部门",
                    parent_external_id=str(item.get("parentid")) if item.get("parentid") not in (None, 0, "0") else None,
                    sort=int(item.get("order") or 0),
                    raw=item,
                )
                for item in dept_data.get("department", [])
                if item.get("id") is not None
            ]

            users_by_id: dict[str, ContactUser] = {}
            for dept in departments:
                user_resp = await client.get(
                    "https://qyapi.weixin.qq.com/cgi-bin/user/list",
                    params={
                        "access_token": access_token,
                        "department_id": dept.external_id,
                        "fetch_child": 0,
                    },
                )
                user_data = self._safe_json(user_resp)
                self._ensure_success(user_data, f"获取企业微信部门「{dept.name}」用户失败")
                for item in user_data.get("userlist", []):
                    external_id = item.get("userid")
                    if not external_id:
                        continue
                    dept_ids = [str(dept_id) for dept_id in item.get("department", []) if dept_id is not None]
                    existing = users_by_id.get(str(external_id))
                    merged_dept_ids = sorted(set((existing.department_external_ids if existing else []) + dept_ids))
                    users_by_id[str(external_id)] = ContactUser(
                        external_id=str(external_id),
                        name=item.get("name") or str(external_id),
                        nickname=item.get("alias") or None,
                        email=item.get("email") or item.get("biz_mail") or None,
                        phone=item.get("mobile") or None,
                        avatar=item.get("avatar") or item.get("thumb_avatar") or None,
                        department_external_ids=merged_dept_ids,
                        active=item.get("enable", 1) == 1,
                        raw=item,
                    )

        return ContactSyncData(departments=departments, users=list(users_by_id.values()))

    async def _get_access_token(self, ctx: AdapterContext) -> str:
        corp_id = ctx.secret_config.get("corp_id")
        corp_secret = ctx.secret_config.get("corp_secret")
        if not corp_id or not corp_secret:
            raise ValueError("缺少企业微信 corp_id 或 corp_secret")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                params={"corpid": corp_id, "corpsecret": corp_secret},
            )
            data = self._safe_json(resp)
        self._ensure_success(data, "获取企业微信 access_token 失败")
        return str(data["access_token"])

    @staticmethod
    def _ensure_success(data: dict[str, Any], default_message: str) -> None:
        if data.get("errcode") not in (0, None):
            raise ValueError(data.get("errmsg") or default_message)

    def _build_webhook_payload(self, *, message_type: str, title: str | None, content: str) -> dict[str, Any]:
        if message_type == "markdown":
            text = f"### {title}\n{content}" if title else content
            return {"msgtype": "markdown", "markdown": {"content": text}}
        return {"msgtype": "text", "text": {"content": f"{title}\n{content}" if title else content}}
