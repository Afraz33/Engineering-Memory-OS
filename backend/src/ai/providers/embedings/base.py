from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


class ProviderError(RuntimeError):
    """Raised when an upstream provider call fails."""


@dataclass(slots=True)
class EmbeddingResponse:
    vectors: list[list[float]]   # batch support
    model: str
    provider: str


class EmbeddingProvider(ABC):
    """
    Provider-agnostic embedding interface.

    Input  → text(s)
    Output → vector(s)
    """

    name: str
    default_model: str
    dimension: int

    @abstractmethod
    async def embed(
        self,
        texts: Sequence[str],
    ) -> EmbeddingResponse:
        """
        Batch embedding.

        Must return vectors in same order as input.
        """