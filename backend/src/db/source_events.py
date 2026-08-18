"""The connector-agnostic half of the capture tables.

Every connector — Slack, Jira, whatever comes next — writes the same two facts:
"this arrived" and "here is what the pipeline decided about it". That is one
table (`source_events`) and one set of queries, which is why these live here
rather than a copy per connector. The `source` column is the only thing that
distinguishes them, and it is a parameter everywhere below.

Two jobs, both worth stating plainly:

  * idempotency — `record_source_event` returns None for an `external_id`
    already seen, so a webhook retry becomes a no-op instead of a duplicate
    memory. Slack retries three times; Jira retries too.
  * audit — an event the classifier threw away still leaves a row saying so.
    That is the difference between "nothing worth storing" and a silent bug
    (Scope §6.4).

All functions here are blocking (the pool is sync). Callers on the event loop
must wrap them in `asyncio.to_thread`; the webhook handlers do.
"""

import json
from typing import Any

from db.session import get_conn


def record_source_event(
    *,
    workspace_id: str,
    source: str,
    external_id: str,
    author: str | None,
    text: str | None,
    occurred_at: Any,
    payload: dict,
) -> str | None:
    """Claim an event for processing.

    Returns the new row's id, or `None` if this `external_id` was already seen —
    which is the whole idempotency mechanism. Connectors retry any delivery they
    think failed, so without this a slow classifier turns one message into three
    identical memories.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_events
                (workspace_id, source, external_id, author, text, occurred_at, payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s::JSONB)
            ON CONFLICT (workspace_id, external_id) DO NOTHING
            RETURNING id;
            """,
            (
                workspace_id,
                source,
                external_id,
                author,
                text,
                occurred_at,
                json.dumps(payload),
            ),
        )
        row = cur.fetchone()
        return str(row["id"]) if row else None


def finish_source_event(
    event_id: str,
    *,
    outcome: str,
    reason: str,
    memory_id: str | None = None,
) -> None:
    """Close the loop on a claimed event. Every path through the pipeline calls
    this, including failures — a row stuck at 'pending' means we crashed."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE source_events
            SET outcome = %s, reason = %s, memory_id = %s, processed_at = now()
            WHERE id = %s;
            """,
            (outcome, reason, memory_id, event_id),
        )


def recent_source_events(
    workspace_id: str, limit: int = 25, source: str | None = None
) -> list[dict]:
    """The audit feed. `source` is optional so a caller can ask for one
    connector's events (what each Sources card wants) or all of them.

    The predicate is assembled in Python rather than written as a
    `%s IS NULL OR source = %s` catch-all: that form forces the planner to give
    up the (workspace_id, source, received_at) index, which is the one this
    query exists to use.
    """
    filters = ["e.workspace_id = %s"]
    params: list[Any] = [workspace_id]
    if source is not None:
        filters.append("e.source = %s")
        params.append(source)
    params.append(limit)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT e.id, e.source, e.external_id, e.author, e.text, e.occurred_at,
                   e.outcome, e.reason, e.memory_id, e.received_at,
                   m.title AS memory_title, m.type AS memory_type
            FROM source_events e
            LEFT JOIN memories m ON m.id = e.memory_id
            WHERE {" AND ".join(filters)}
            ORDER BY e.received_at DESC
            LIMIT %s;
            """,
            tuple(params),
        )
        return cur.fetchall()


def source_event_stats(workspace_id: str, source: str) -> dict:
    """Counts for the Sources page: how much came in, how much survived."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                count(*)                                              AS received,
                count(*) FILTER (WHERE outcome = 'stored')            AS stored,
                count(*) FILTER (WHERE outcome = 'quarantined')       AS quarantined,
                count(*) FILTER (WHERE outcome LIKE 'dropped%%')      AS dropped,
                count(*) FILTER (WHERE outcome IN ('pending','error')) AS unfinished,
                max(received_at)                                      AS last_event_at
            FROM source_events
            WHERE workspace_id = %s AND source = %s;
            """,
            (workspace_id, source),
        )
        return cur.fetchone()
