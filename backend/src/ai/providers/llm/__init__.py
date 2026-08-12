"""LLM provider registry.

`LLM_PROVIDER` selects the adapter at startup. Provider SDKs are imported
lazily inside each adapter, so only the one you actually use needs to be
installed.
"""

import os
from functools import lru_cache

from ai.providers.llm.base import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    ProviderError,
    Role,
    Usage,
)

__all__ = [
    "ChatMessage",
    "ChatProvider",
    "ChatResponse",
    "ProviderError",
    "Role",
    "Usage",
    "get_provider",
]


def _gemini() -> ChatProvider:
    from ai.providers.llm.gemini import GeminiProvider

    return GeminiProvider()


def _anthropic() -> ChatProvider:
    from ai.providers.llm.anthropic import AnthropicProvider

    return AnthropicProvider()


def _openai() -> ChatProvider:
    from ai.providers.llm.openai import OpenAIProvider

    return OpenAIProvider()


def _ollama() -> ChatProvider:
    from ai.providers.llm.ollama import OllamaProvider

    return OllamaProvider()


PROVIDERS = {
    "gemini": _gemini,
    "anthropic": _anthropic,
    "openai": _openai,
    "ollama": _ollama,
}


@lru_cache(maxsize=None)
def get_provider(name: str | None = None) -> ChatProvider:
    name = (name or os.getenv("LLM_PROVIDER", "gemini")).lower()
    try:
        factory = PROVIDERS[name]
    except KeyError:
        known = ", ".join(sorted(PROVIDERS))
        raise ProviderError(f"unknown LLM_PROVIDER {name!r} (expected one of: {known})") from None
    return factory()
