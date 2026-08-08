from __future__ import annotations

import uuid
from typing import Callable

from sqlalchemy.orm import Session

from app.db.embeddings.dao import EmbeddingsDAO
from app.db.embeddings.types import EmbeddingVector, SimilarityResult
from app.db.models.embeddings import Embedding

_METRIC_OPERATORS: dict[str, str] = {"cosine": "<=>", "dot": "<#>", "l2": "<->"}


class EmbeddingsRepository:
    def __init__(self, session: Session) -> None:
        self._dao = EmbeddingsDAO(session)

    def store(self, content: str, embedding: EmbeddingVector, model: str,
              namespace: str = "default", meta: dict | None = None) -> uuid.UUID:
        return self._dao.insert(content=content, embedding=embedding, model=model,
                                namespace=namespace, meta=meta or {}).id

    def store_many(self, records: list[dict]) -> list[uuid.UUID]:
        return [o.id for o in self._dao.insert_many(records)]

    def get_by_id(self, record_id: uuid.UUID) -> Embedding | None:
        return self._dao.get_by_id(record_id)

    def list_by_namespace(self, namespace: str, limit: int = 100, offset: int = 0) -> list[Embedding]:
        return self._dao.list_by_namespace(namespace, limit=limit, offset=offset)

    def search_cosine(self, query_embedding: EmbeddingVector, namespace: str | None = None,
                      top_k: int = 10, threshold: float = 0.0) -> list[SimilarityResult]:
        return self._search(query_embedding, "<=>", lambda d: 1.0 - d, namespace, top_k, threshold, 2.0)

    def search_dot_product(self, query_embedding: EmbeddingVector, namespace: str | None = None,
                           top_k: int = 10, threshold: float = 0.0) -> list[SimilarityResult]:
        return self._search(query_embedding, "<#>", lambda d: -d, namespace, top_k, threshold, 1e9)

    def search_l2(self, query_embedding: EmbeddingVector, namespace: str | None = None,
                  top_k: int = 10, max_distance: float = float("inf")) -> list[SimilarityResult]:
        return self._search(query_embedding, "<->", lambda d: d, namespace, top_k,
                            -float("inf"), max_distance if max_distance != float("inf") else 1e9)

    def compare(self, id_a: uuid.UUID, id_b: uuid.UUID, metric: str = "cosine") -> float:
        if metric not in _METRIC_OPERATORS:
            raise ValueError(f"Unknown metric {metric!r}. Choose from: {list(_METRIC_OPERATORS)}")
        if self._dao.get_by_id(id_a) is None:
            raise ValueError(f"No embedding found with id={id_a}")
        if self._dao.get_by_id(id_b) is None:
            raise ValueError(f"No embedding found with id={id_b}")
        raw = self._dao.distance_between(id_a, id_b, _METRIC_OPERATORS[metric])
        if metric == "cosine":
            return 1.0 - raw
        if metric == "dot":
            return -raw
        return raw

    def delete_by_id(self, record_id: uuid.UUID) -> bool:
        return self._dao.delete_by_id(record_id) > 0

    def delete_namespace(self, namespace: str) -> int:
        return self._dao.delete_by_namespace(namespace)

    def _search(self, query_embedding: EmbeddingVector, operator: str,
                distance_to_score: Callable[[float], float], namespace: str | None,
                top_k: int, threshold: float, max_distance: float) -> list[SimilarityResult]:
        rows = self._dao.vector_search(query_embedding, operator, namespace, top_k, max_distance)
        results = []
        for row in rows:
            score = distance_to_score(float(row.raw_distance))
            if score < threshold:
                continue
            results.append(SimilarityResult(
                id=row.id, content=row.content, namespace=row.namespace,
                model=row.model, meta=row.meta, created_at=row.created_at, score=score,
            ))
        return results
