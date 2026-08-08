"""
Shared types for the embeddings layer.

Imported by both DAO and Repository — neither depends on the other for types.
"""

from __future__ import annotations

import uuid
from typing import Any


# A flat list of floats produced by any embedding model.
EmbeddingVector = list[float]


class SimilarityResult:
    """
    A single hit returned by a vector similarity search.

    score semantics
    ---------------
    - cosine / dot:  higher → more similar  (range roughly 0 – 1)
    - l2:            lower  → more similar  (raw Euclidean distance)
    """

    __slots__ = ("id", "content", "namespace", "model", "meta", "created_at", "score")

    def __init__(
        self,
        *,
        id: uuid.UUID,
        content: str,
        namespace: str,
        model: str,
        meta: dict,
        created_at: Any,
        score: float,
    ) -> None:
        self.id = id
        self.content = content
        self.namespace = namespace
        self.model = model
        self.meta = meta
        self.created_at = created_at
        self.score = score

    def __repr__(self) -> str:
        return (
            f"SimilarityResult(id={self.id}, score={self.score:.4f}, "
            f"namespace={self.namespace!r})"
        )
