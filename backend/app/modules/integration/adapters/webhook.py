"""机器人 Webhook 类平台的公共实现。"""
from typing import Any

import httpx

from app.modules.integration.adapters.base import AdapterContext, AdapterResult, CollaborationAdapter


class WebhookAdapter(CollaborationAdapter):
    required_secret_fields = []
    optional_secret_fields = ["webhook_url", "signing_secret"]
    capabilities = ["bot_message"]

    async def test(self, ctx: AdapterContext) -> AdapterResult:
        secret = ctx.secret_config
        if secret.get("app_id") and secret.get("app_secret"):
            return await self._test_app_credentials(ctx)
        if secret.get("corp_id") and secret.get("corp_secret"):
            return await self._test_app_credentials(ctx)
        if secret.get("webhook_url"):
            return AdapterResult(success=True, message="机器人 Webhook 已配置")
        return AdapterResult(success=False, message="缺少可测试的凭证或机器人 Webhook")

    async def send_message(
        self,
        ctx: AdapterContext,
        *,
        message_type: str,
        title: str | None,
        content: str,
        target: dict[str, Any],
        metadata: dict[str, Any],
    ) -> AdapterResult:
        _ = (target, metadata)
        webhook_url = ctx.secret_config.get("webhook_url")
        if not webhook_url:
            return AdapterResult(success=False, message="未配置机器人 Webhook")

        payload = self._build_webhook_payload(message_type=message_type, title=title, content=content)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload)
                data = self._safe_json(resp)
        except httpx.HTTPError as exc:
            return AdapterResult(success=False, message=f"平台请求失败: {exc}")

        if self._is_success(data, resp.status_code):
            return AdapterResult(success=True, message="发送成功", details=data)
        return AdapterResult(
            success=False,
            message=self._error_message(data, resp.status_code),
            details=data,
        )

    async def _test_app_credentials(self, ctx: AdapterContext) -> AdapterResult:
        _ = ctx
        return AdapterResult(success=True, message="当前适配器未实现应用凭证测试")

    def _build_webhook_payload(self, *, message_type: str, title: str | None, content: str) -> dict[str, Any]:
        raise NotImplementedError

    def _is_success(self, data: dict[str, Any], status_code: int) -> bool:
        if status_code >= 400:
            return False
        code = data.get("code", data.get("errcode"))
        return code in (None, 0)

    def _error_message(self, data: dict[str, Any], status_code: int) -> str:
        message = data.get("msg") or data.get("errmsg") or data.get("message")
        return f"发送失败: {message or f'HTTP {status_code}'}"

    @staticmethod
    def _safe_json(resp: httpx.Response) -> dict[str, Any]:
        try:
            data = resp.json()
            return data if isinstance(data, dict) else {"data": data}
        except ValueError:
            return {"text": resp.text}
