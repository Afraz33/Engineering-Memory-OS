from __future__ import annotations

import uuid
from typing import Any, Sequence

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.models.embeddings import Embedding
from app.db.embeddings.types import EmbeddingVector


class EmbeddingsDAO:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(self, content: str, embedding: EmbeddingVector, model: str, namespace: str, meta: dict) -> Embedding:
        record = Embedding(content=content, embedding=embedding, model=model, namespace=namespace, meta=meta)
        self._session.add(record)
        self._session.flush()
        return record

    def insert_many(self, rows: list[dict]) -> list[Embedding]:
        objs = [
            Embedding(
                content=r["content"], embedding=r["embedding"], model=r["model"],
                namespace=r.get("namespace", "default"), meta=r.get("meta", {}),
            )
            for r in rows
        ]
        self._session.add_all(objs)
        self._session.flush()
        return objs

    def get_by_id(self, record_id: uuid.UUID) -> Embedding | None:
        return self._session.get(Embedding, record_id)

    def list_by_namespace(self, namespace: str, limit: int, offset: int) -> list[Embedding]:
        stmt = (
            select(Embedding).where(Embedding.namespace == namespace)
            .order_by(Embedding.created_at.desc()).limit(limit).offset(offset)
        )
        return list(self._session.scalars(stmt))

    def vector_search(self, query_embedding: EmbeddingVector, operator: str,
                      namespace: str | None, top_k: int, max_distance: float) -> Sequence[Any]:
        vec_literal = f"[{','.join(str(v) for v in query_embedding)}]"
        where_clauses = [f"embedding {operator} :query_vec::vector < :max_dist"]
        params: dict[str, Any] = {"query_vec": vec_literal, "max_dist": max_distance, "top_k": top_k}
        if namespace is not None:
            where_clauses.append("namespace = :namespace")
            params["namespace"] = namespace
        where_sql = " AND ".join(where_clauses)
        sql = text(f"""
            SELECT id, content, namespace, model, meta, created_at,
                   embedding {operator} :query_vec::vector AS raw_distance
            FROM embeddings WHERE {where_sql}
            ORDER BY embedding {operator} :query_vec::vector ASC
            LIMIT :top_k
        """)
        return self._session.execute(sql, params).fetchall()

    def distance_between(self, id_a: uuid.UUID, id_b: uuid.UUID, operator: str) -> float:
        result = self._session.execute(
            text(f"SELECT embedding {operator} (SELECT embedding FROM embeddings WHERE id = :b) "
                 f"FROM embeddings WHERE id = :a"),
            {"a": str(id_a), "b": str(id_b)},
        ).scalar_one()
        return float(result)

    def delete_by_id(self, record_id: uuid.UUID) -> int:
        return self._session.execute(delete(Embedding).where(Embedding.id == record_id)).rowcount

    def delete_by_namespace(self, namespace: str) -> int:
        return self._session.execute(delete(Embedding).where(Embedding.namespace == namespace)).rowcount
