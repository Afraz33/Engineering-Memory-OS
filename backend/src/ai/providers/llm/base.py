"""Provider-agnostic chat interface.

Every provider adapter speaks these types, so swapping providers is an env
var change (`LLM_PROVIDER`) rather than a code change at the call site.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal

Role = Literal["user", "assistant"]


class ProviderError(RuntimeError):
    """Raised when an upstream provider call fails."""


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class ChatResponse:
    content: str
    model: str
    provider: str
    usage: Usage


class ChatProvider(ABC):
    """A chat-completion backend.

    Implementations must not leak provider SDK types across this boundary —
    everything in and out is the dataclasses above.
    """

    name: str
    default_model: str

    @abstractmethod
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> ChatResponse:
        """Return the full assistant reply."""

    @abstractmethod
    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield the assistant reply as text deltas."""
