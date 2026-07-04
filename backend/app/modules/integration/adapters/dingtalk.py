"""钉钉适配器。"""
from typing import Any

import httpx

from app.modules.integration.adapters.base import AdapterContext, AdapterResult
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

    def _build_webhook_payload(self, *, message_type: str, title: str | None, content: str) -> dict[str, Any]:
        if message_type == "markdown":
            return {
                "msgtype": "markdown",
                "markdown": {"title": title or "通知", "text": f"### {title}\n{content}" if title else content},
            }
        return {"msgtype": "text", "text": {"content": f"{title}\n{content}" if title else content}}
