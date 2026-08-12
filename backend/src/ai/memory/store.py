"""Memory persistence.

`MemoryStore` is the seam. Everything upstream (capture, retrieval) talks to
this interface, so the CockroachDB + pgvector implementation lands as a second
class rather than as a rewrite of the callers.

`InMemoryMemoryStore` is process-local and dies with the worker. It exists so
the capture pipeline can be built and exercised before the schema and
migrations land (Scope §10, "nothing commits to the database").
"""

# `MemoryStore.list` shadows the builtin inside the class body, so a
# `-> list[Memory]` annotation on a later method would be evaluated against the
# method object. Deferring annotations sidesteps it without renaming the ABC.
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache

from ai.memory.models import Memory, MemoryStatus, MemoryType, Provenance

log = logging.getLogger(__name__)


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


class PostgresMemoryStore(MemoryStore):
    """The real one: CockroachDB, via the pool in `db.session`.

    Every method hops to a worker thread. The pool is blocking and these are
    called from `async def` handlers, so running the SQL inline would stall the
    event loop for the duration of the round trip.
    """

    async def add(self, memory: Memory) -> Memory:
        await asyncio.to_thread(self._insert, memory)

        # Embedding failure must not lose the memory: the row is already
        # committed above, and a record with no vector is merely invisible to
        # semantic search until backfilled, whereas raising here would discard
        # an extraction we already paid an LLM call for.
        try:
            from services.embedding_service import add_embedding

            await add_embedding(memory.id, f"{memory.title}\n\n{memory.body}")
        except Exception as exc:  # noqa: BLE001 - provider errors are open-ended
            log.warning("embedding failed for memory %s: %s", memory.id, exc)

        return memory

    @staticmethod
    def _insert(memory: Memory) -> None:
        from db.session import get_conn

        # One transaction: a memory whose provenance failed to write is exactly
        # the unattributable record `Memory.__post_init__` refuses to construct.
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memories
                    (id, workspace_id, type, title, body, scope, status,
                     confidence, entities, superseded_by, valid_from, valid_until,
                     created_at, last_accessed_at, access_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::JSONB, %s, %s, %s, %s, %s, %s);
                """,
                (
                    memory.id,
                    memory.workspace_id,
                    memory.type,
                    memory.title,
                    memory.body,
                    memory.scope,
                    memory.status,
                    memory.confidence,
                    json.dumps(memory.entities),
                    memory.superseded_by,
                    memory.valid_from,
                    memory.valid_until,
                    memory.created_at,
                    memory.last_accessed_at,
                    memory.access_count,
                ),
            )
            cur.executemany(
                """
                INSERT INTO memory_provenance
                    (id, memory_id, source, author, url, excerpt)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                [
                    (
                        str(uuid.uuid4()),
                        memory.id,
                        p.source,
                        p.author,
                        p.url,
                        p.excerpt,
                    )
                    for p in memory.provenance
                ],
            )

    async def get(self, memory_id: str) -> Memory | None:
        rows = await asyncio.to_thread(self._select, [memory_id], None, None, None, None)
        return rows[0] if rows else None

    async def list(
        self,
        *,
        workspace_id: str | None = None,
        scope: str | None = None,
        types: Sequence[MemoryType] | None = None,
        statuses: Sequence[MemoryStatus] | None = None,
    ) -> list[Memory]:
        return await asyncio.to_thread(
            self._select, None, workspace_id, scope, types, statuses
        )

    @staticmethod
    def _select(
        ids: Sequence[str] | None,
        workspace_id: str | None,
        scope: str | None,
        types: Sequence[MemoryType] | None,
        statuses: Sequence[MemoryStatus] | None,
    ) -> list[Memory]:
        from db.session import get_conn

        where: list[str] = []
        params: list[object] = []
        if ids is not None:
            where.append("id = ANY(%s)")
            params.append(list(ids))
        if workspace_id is not None:
            where.append("workspace_id = %s")
            params.append(workspace_id)
        if scope is not None:
            where.append("scope = %s")
            params.append(scope)
        if types:
            where.append("type = ANY(%s)")
            params.append(list(types))
        if statuses:
            where.append("status = ANY(%s)")
            params.append(list(statuses))

        clause = f"WHERE {' AND '.join(where)}" if where else ""

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM memories {clause} ORDER BY created_at DESC;",
                params,
            )
            rows = cur.fetchall()
            if not rows:
                return []

            cur.execute(
                """
                SELECT memory_id, source, author, url, excerpt, created_at
                FROM memory_provenance
                WHERE memory_id = ANY(%s);
                """,
                ([row["id"] for row in rows],),
            )
            prov_rows = cur.fetchall()

        by_memory: dict[str, list[Provenance]] = {}
        for p in prov_rows:
            by_memory.setdefault(str(p["memory_id"]), []).append(
                Provenance(
                    source=p["source"] or "",
                    author=p["author"] or "unknown",
                    ts=_as_utc(p["created_at"]),
                    excerpt=p["excerpt"] or "",
                    url=p["url"],
                )
            )

        return [_row_to_memory(row, by_memory) for row in rows]

    async def delete(self, memory_id: str) -> bool:
        return await asyncio.to_thread(self._delete, memory_id)

    @staticmethod
    def _delete(memory_id: str) -> bool:
        from db.session import get_conn

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM memories WHERE id = %s;", (memory_id,))
            return cur.rowcount > 0


def _as_utc(value: datetime | None) -> datetime:
    """TIMESTAMP columns come back naive. Re-attach UTC so callers never end up
    comparing a naive value against an aware one and raising mid-sort."""
    if value is None:
        return datetime.now(UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _row_to_memory(row: dict, provenance: dict[str, list[Provenance]]) -> Memory:
    memory_id = str(row["id"])
    prov = provenance.get(memory_id)
    if not prov:
        # `Memory` refuses to construct without provenance, and a store read is
        # the wrong place to enforce a write-side invariant. Stand in a marker
        # so one bad legacy row cannot break every list() call.
        prov = [
            Provenance(
                source="unknown",
                author="unknown",
                ts=_as_utc(row.get("created_at")),
                excerpt="",
            )
        ]

    return Memory(
        id=memory_id,
        workspace_id=row["workspace_id"],
        type=row["type"],
        title=row["title"],
        body=row["body"],
        scope=row["scope"] or "workspace",
        status=row["status"] or "active",
        confidence=float(row["confidence"] or 0.0),
        entities=list(row["entities"] or []),
        superseded_by=str(row["superseded_by"]) if row["superseded_by"] else None,
        provenance=prov,
        valid_from=_as_utc(row["valid_from"]),
        valid_until=row["valid_until"],
        created_at=_as_utc(row["created_at"]),
        last_accessed_at=row["last_accessed_at"],
        access_count=row["access_count"] or 0,
    )


@lru_cache(maxsize=1)
def get_store() -> MemoryStore:
    """Postgres by default. `MEMORY_STORE=memory` opts back into the throwaway
    dict — useful for tests and for poking at the pipeline with no database up.
    """
    if os.getenv("MEMORY_STORE", "postgres").lower() == "memory":
        return InMemoryMemoryStore(
            capacity=int(os.getenv("MEMORY_STORE_CAPACITY", "10000"))
        )
    return PostgresMemoryStore()
