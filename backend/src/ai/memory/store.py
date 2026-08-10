"""Memory persistence.

`MemoryStore` is the seam. Everything upstream (capture, retrieval) talks to
this interface, so the CockroachDB + pgvector implementation lands as a second
class rather than as a rewrite of the callers.

`InMemoryMemoryStore` is process-local and dies with the worker. It exists so
the capture pipeline can be built and exercised before the schema and
migrations land (Scope §10, "nothing commits to the database").
"""

import os
from abc import ABC, abstractmethod
from collections.abc import Sequence
from functools import lru_cache

from ai.memory.models import Memory, MemoryStatus, MemoryType


class MemoryStore(ABC):
    @abstractmethod
    async def add(self, memory: Memory) -> Memory:
        """Persist a record and return it."""

    @abstractmethod
    async def get(self, memory_id: str) -> Memory | None:
        """Return one record, or None."""

    @abstractmethod
    async def list(
        self,
        *,
        workspace_id: str | None = None,
        scope: str | None = None,
        types: Sequence[MemoryType] | None = None,
        statuses: Sequence[MemoryStatus] | None = None,
    ) -> list[Memory]:
        """Return records matching every supplied filter, newest first."""

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Remove a record. Returns whether it existed."""


class InMemoryMemoryStore(MemoryStore):
    def __init__(self, capacity: int = 10_000):
        self._records: dict[str, Memory] = {}
        self._capacity = capacity

    async def add(self, memory: Memory) -> Memory:
        # Unbounded growth in a process-local dict is a slow leak, not a
        # feature. Evict oldest-first; the real store has no such limit.
        if len(self._records) >= self._capacity:
            oldest = min(self._records.values(), key=lambda m: m.created_at)
            self._records.pop(oldest.id, None)
        self._records[memory.id] = memory
        return memory

    async def get(self, memory_id: str) -> Memory | None:
        return self._records.get(memory_id)

    async def list(
        self,
        *,
        workspace_id: str | None = None,
        scope: str | None = None,
        types: Sequence[MemoryType] | None = None,
        statuses: Sequence[MemoryStatus] | None = None,
    ) -> list[Memory]:
        results = list(self._records.values())
        if workspace_id is not None:
            results = [m for m in results if m.workspace_id == workspace_id]
        if scope is not None:
            results = [m for m in results if m.scope == scope]
        if types:
            allowed = set(types)
            results = [m for m in results if m.type in allowed]
        if statuses:
            allowed_status = set(statuses)
            results = [m for m in results if m.status in allowed_status]
        results.sort(key=lambda m: m.created_at, reverse=True)
        return results

    async def delete(self, memory_id: str) -> bool:
        return self._records.pop(memory_id, None) is not None


@lru_cache(maxsize=1)
def get_store() -> MemoryStore:
    return InMemoryMemoryStore(
        capacity=int(os.getenv("MEMORY_STORE_CAPACITY", "10000"))
    )
