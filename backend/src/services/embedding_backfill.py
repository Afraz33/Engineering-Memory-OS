"""Embed memories that have no vector yet.

Two ways to end up here. `PostgresMemoryStore.add` deliberately swallows
embedding failures -- the memory is already committed and losing an LLM
extraction over a provider blip is the worse trade -- so a provider outage
leaves rows behind. And anything captured before the vector index existed at
all never had one written.

A memory with no vector is not broken, just invisible to semantic search. This
puts it back.

    uv run backfill-embeddings              # everything missing
    uv run backfill-embeddings --limit 100  # a bite at a time
"""

import argparse
import asyncio
import logging

from db.session import get_conn
from services.embedding_service import add_embedding

log = logging.getLogger(__name__)


def _missing(limit: int | None) -> list[tuple[str, str, str]]:
    """(memory_id, workspace_id, text) for memories with no embedding row."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.id, m.workspace_id, m.title, m.body
            FROM memories m
            LEFT JOIN embeddings e ON e.memory_id = m.id
            WHERE e.memory_id IS NULL
            ORDER BY m.created_at DESC
            {};
            """.format("LIMIT %s" if limit else ""),
            (limit,) if limit else (),
        )
        return [
            (str(r["id"]), r["workspace_id"], f"{r['title']}\n\n{r['body']}")
            for r in cur.fetchall()
        ]


async def _run(limit: int | None) -> None:
    rows = _missing(limit)
    if not rows:
        print("Nothing to backfill: every memory has an embedding.")
        return

    print(f"Embedding {len(rows)} memories...")
    done = failed = 0
    for memory_id, workspace_id, text in rows:
        try:
            await add_embedding(memory_id, workspace_id, text)
            done += 1
        except Exception as exc:  # noqa: BLE001 - provider errors are open-ended
            # One bad row must not abandon the rest of the batch; it stays
            # missing and the next run picks it up again.
            failed += 1
            log.warning("backfill failed for %s: %s", memory_id, exc)

    print(f"Embedded {done}, failed {failed}.")


def backfill_embeddings() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="stop after N memories (each one is a provider call)",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.limit))


if __name__ == "__main__":
    backfill_embeddings()
