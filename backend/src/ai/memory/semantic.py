from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.semantic_memory.dao import SemanticMemoryDAO
from ai.memory.working import WorkingMemory


class SemanticMemory:
    def __init__(self, session: Session, namespace: str = "default") -> None:
        self._dao = SemanticMemoryDAO(session)
        self._namespace = namespace

    def get(self, key: str) -> str | None:
        return self._dao.get(namespace=self._namespace, key=key)

    def set(self, key: str, value: str) -> None:
        self._dao.upsert(namespace=self._namespace, key=key, value=value)

    def delete(self, key: str) -> bool:
        return self._dao.delete(namespace=self._namespace, key=key)

    def list_keys(self) -> list[str]:
        return self._dao.list_keys(namespace=self._namespace)

    def get_many(self, keys: list[str]) -> dict[str, str]:
        return self._dao.get_many(namespace=self._namespace, keys=keys)

    def inject_into(self, working: WorkingMemory, keys: list[str]) -> None:
        for key, value in self.get_many(keys).items():
            working.set_snippet(key, value)

    def inject_all_into(self, working: WorkingMemory) -> None:
        keys = self.list_keys()
        if keys:
            self.inject_into(working, keys)

    @property
    def namespace(self) -> str:
        return self._namespace
