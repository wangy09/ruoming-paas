"""企业微信适配器。"""
from typing import Any

import httpx

from app.modules.integration.adapters.base import AdapterContext, AdapterResult
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

    def _build_webhook_payload(self, *, message_type: str, title: str | None, content: str) -> dict[str, Any]:
        if message_type == "markdown":
            text = f"### {title}\n{content}" if title else content
            return {"msgtype": "markdown", "markdown": {"content": text}}
        return {"msgtype": "text", "text": {"content": f"{title}\n{content}" if title else content}}
