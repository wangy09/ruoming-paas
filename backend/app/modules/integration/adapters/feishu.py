"""飞书适配器。"""
from typing import Any

import httpx

from app.modules.integration.adapters.base import AdapterContext, AdapterResult
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

    def _build_webhook_payload(self, *, message_type: str, title: str | None, content: str) -> dict[str, Any]:
        if message_type == "markdown":
            text = f"**{title}**\n{content}" if title else content
            return {"msg_type": "interactive", "card": {"elements": [{"tag": "markdown", "content": text}]}}
        return {"msg_type": "text", "content": {"text": f"{title}\n{content}" if title else content}}
