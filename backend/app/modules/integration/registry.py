"""第三方协作平台适配器注册表。"""
from app.modules.integration.adapters.base import CollaborationAdapter
from app.modules.integration.adapters.dingtalk import DingTalkAdapter
from app.modules.integration.adapters.feishu import FeishuAdapter
from app.modules.integration.adapters.wecom import WeComAdapter
from app.modules.integration.schemas import ProviderInfo


class IntegrationRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, CollaborationAdapter] = {}
        self.register(FeishuAdapter())
        self.register(DingTalkAdapter())
        self.register(WeComAdapter())

    def register(self, adapter: CollaborationAdapter) -> None:
        self._adapters[adapter.provider] = adapter

    def get(self, provider: str) -> CollaborationAdapter:
        adapter = self._adapters.get(provider)
        if not adapter:
            raise KeyError(provider)
        return adapter

    def list_providers(self) -> list[ProviderInfo]:
        return [
            ProviderInfo(
                code=adapter.provider,  # type: ignore[arg-type]
                name=adapter.name,
                capabilities=adapter.capabilities,  # type: ignore[arg-type]
                required_secret_fields=adapter.required_secret_fields,
                optional_secret_fields=adapter.optional_secret_fields,
                config_fields=adapter.config_fields,
            )
            for adapter in self._adapters.values()
        ]


integration_registry = IntegrationRegistry()
