from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from ai.providers.types import ChatMessage, EmbeddingVector


class BaseProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.7,
                   max_tokens: int | None = None) -> str: ...

    @abstractmethod
    async def stream(self, messages: list[ChatMessage], *, temperature: float = 0.7,
                     max_tokens: int | None = None) -> AsyncIterator[str]: ...

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingVector: ...

    @abstractmethod
    async def close(self) -> None: ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider_name!r}, model={self.model_name!r})"
