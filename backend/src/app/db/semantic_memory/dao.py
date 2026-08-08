from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.semantic_memory import SemanticMemoryEntry


class SemanticMemoryDAO:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, namespace: str, key: str) -> str | None:
        row = self._session.get(SemanticMemoryEntry, (namespace, key))
        return row.value if row else None

    def get_many(self, namespace: str, keys: list[str]) -> dict[str, str]:
        stmt = select(SemanticMemoryEntry).where(
            SemanticMemoryEntry.namespace == namespace,
            SemanticMemoryEntry.key.in_(keys),
        )
        return {row.key: row.value for row in self._session.scalars(stmt).all()}

    def list_keys(self, namespace: str) -> list[str]:
        stmt = select(SemanticMemoryEntry.key).where(SemanticMemoryEntry.namespace == namespace)
        return list(self._session.scalars(stmt).all())

    def list_all(self, namespace: str) -> dict[str, str]:
        stmt = select(SemanticMemoryEntry).where(SemanticMemoryEntry.namespace == namespace)
        return {row.key: row.value for row in self._session.scalars(stmt).all()}

    def upsert(self, namespace: str, key: str, value: str) -> None:
        stmt = (
            insert(SemanticMemoryEntry)
            .values(namespace=namespace, key=key, value=value)
            .on_conflict_do_update(index_elements=["namespace", "key"], set_={"value": value})
        )
        self._session.execute(stmt)

    def delete(self, namespace: str, key: str) -> bool:
        return self._session.execute(
            delete(SemanticMemoryEntry).where(
                SemanticMemoryEntry.namespace == namespace,
                SemanticMemoryEntry.key == key,
            )
        ).rowcount > 0

    def delete_namespace(self, namespace: str) -> int:
        return self._session.execute(
            delete(SemanticMemoryEntry).where(SemanticMemoryEntry.namespace == namespace)
        ).rowcount
