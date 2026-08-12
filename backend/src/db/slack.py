"""Queries for the Slack connector: installations and raw inbound events.

Kept out of `db/models.py` because these two tables belong to the connector, not
to the memory domain — the rest of the app never reads them.

All functions here are blocking (the pool is sync). Callers on the event loop
must wrap them in `asyncio.to_thread`; the webhook handler does.
"""

import json
from typing import Any

from db.session import get_conn

# --- installations ----------------------------------------------------------


def upsert_installation(
    *,
    team_id: str,
    team_name: str | None,
    workspace_id: str,
    bot_token: str,
    bot_user_id: str | None,
    installed_by: str | None,
) -> dict:
    """Record (or refresh) an install.

    Conflict is on `team_id`: reinstalling the same Slack workspace issues a new
    bot token and must replace the old one, not add a second row that the
    webhook would then have to choose between.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO slack_installations
                (team_id, team_name, workspace_id, bot_token, bot_user_id, installed_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (team_id) DO UPDATE
                SET team_name    = excluded.team_name,
                    workspace_id = excluded.workspace_id,
                    bot_token    = excluded.bot_token,
                    bot_user_id  = excluded.bot_user_id,
                    installed_by = excluded.installed_by,
                    installed_at = now()
            RETURNING id, team_id, team_name, workspace_id, bot_user_id, installed_at;
            """,
            (team_id, team_name, workspace_id, bot_token, bot_user_id, installed_by),
        )
        return cur.fetchone()


def get_installation_by_team(team_id: str) -> dict | None:
    """Resolve an inbound webhook's `team_id` to a tenant and a bot token."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, team_id, team_name, workspace_id, bot_token, bot_user_id,
                   installed_at
            FROM slack_installations
            WHERE team_id = %s;
            """,
            (team_id,),
        )
        return cur.fetchone()


def get_installation_by_workspace(workspace_id: str) -> dict | None:
    """What the UI asks: is this workspace connected, and to which Slack team?"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, team_id, team_name, workspace_id, bot_user_id, installed_at
            FROM slack_installations
            WHERE workspace_id = %s
            ORDER BY installed_at DESC
            LIMIT 1;
            """,
            (workspace_id,),
        )
        return cur.fetchone()


def delete_installation(workspace_id: str) -> bool:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM slack_installations WHERE workspace_id = %s;",
            (workspace_id,),
        )
        return cur.rowcount > 0


# --- raw events -------------------------------------------------------------


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
    which is the whole idempotency mechanism. Slack retries any delivery it
    thinks failed, so without this a slow classifier turns one message into
    three identical memories.
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


def recent_source_events(workspace_id: str, limit: int = 25) -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id, e.source, e.external_id, e.author, e.text, e.occurred_at,
                   e.outcome, e.reason, e.memory_id, e.received_at,
                   m.title AS memory_title, m.type AS memory_type
            FROM source_events e
            LEFT JOIN memories m ON m.id = e.memory_id
            WHERE e.workspace_id = %s
            ORDER BY e.received_at DESC
            LIMIT %s;
            """,
            (workspace_id, limit),
        )
        return cur.fetchall()


def source_event_stats(workspace_id: str, source: str = "slack") -> dict:
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
