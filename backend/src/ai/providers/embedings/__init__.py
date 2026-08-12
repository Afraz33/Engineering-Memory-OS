"""Embedding provider registry.

`EMBEDDING_PROVIDER` selects the adapter at runtime.
"""

import os
from functools import lru_cache

from ai.providers.embedings.base import (
    EmbeddingProvider,
    EmbeddingResponse,
    ProviderError,
)

__all__ = [
    "EmbeddingProvider",
    "EmbeddingResponse",
    "ProviderError",
    "get_embedding_provider",
]


def _gemini() -> EmbeddingProvider:
    from ai.providers.embedings.gemini import GeminiEmbeddingProvider

    api_key = os.getenv("GOOGLE_API_KEY", "")
    return GeminiEmbeddingProvider(api_key=api_key)


def _ollama() -> EmbeddingProvider:
    from ai.providers.embedings.ollama import OllamaEmbeddingProvider

    return OllamaEmbeddingProvider()


PROVIDERS = {
    "gemini": _gemini,
    "ollama": _ollama,
}


@lru_cache(maxsize=None)
def get_embedding_provider(name: str | None = None) -> EmbeddingProvider:
    name = (name or os.getenv("EMBEDDING_PROVIDER", os.getenv("LLM_PROVIDER", "gemini"))).lower()
    try:
        factory = PROVIDERS[name]
    except KeyError:
        known = ", ".join(sorted(PROVIDERS))
        raise ProviderError(f"unknown EMBEDDING_PROVIDER {name!r} (expected one of: {known})") from None
    return factory()
