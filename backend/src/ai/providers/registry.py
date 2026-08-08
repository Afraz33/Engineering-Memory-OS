from __future__ import annotations

from ai.providers.base import BaseProvider
from ai.providers.types import ChatMessage, EmbeddingVector


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._active: str | None = None

    def register(self, name: str, provider: BaseProvider) -> None:
        self._providers[name] = provider
        if self._active is None:
            self._active = name

    def set_active(self, name: str) -> None:
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' not registered. Available: {list(self._providers)}")
        self._active = name

    def get(self, name: str | None = None) -> BaseProvider:
        if not self._providers:
            raise RuntimeError("No providers registered.")
        target = name or self._active
        if target not in self._providers:
            raise ValueError(f"Provider '{target}' not registered.")
        return self._providers[target]

    @property
    def active_name(self) -> str | None:
        return self._active

    @property
    def available(self) -> list[str]:
        return list(self._providers)

    async def chat(self, messages: list[ChatMessage], **kwargs) -> str:
        return await self.get().chat(messages, **kwargs)

    async def embed(self, text: str) -> EmbeddingVector:
        return await self.get().embed(text)

    async def close_all(self) -> None:
        for provider in self._providers.values():
            await provider.close()


_registry = ProviderRegistry()


def build_default_registry() -> ProviderRegistry:
    if _registry.available:
        return _registry
    import os
    from ai.providers.ollama import OllamaProvider
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    _registry.register("ollama", OllamaProvider(model=model, base_url=base_url))
    return _registry


def get_provider(name: str | None = None) -> BaseProvider:
    return _registry.get(name)


def get_registry() -> ProviderRegistry:
    return _registry
