"""Queries for the Jira connector: installations and raw inbound events.

Jira-specific installation data lives here.

Raw Jira issues reuse the shared `source_events` table, exactly like Slack.
That keeps the memory/knowledge pipeline source-agnostic.

All functions here are blocking (the pool is sync). Callers on the event loop
must wrap them in asyncio.to_thread().
"""

import json
from typing import Any

from db.session import get_conn


# ---------------------------------------------------------------------------
# Installations
# ---------------------------------------------------------------------------

def upsert_installation(
    *,
    cloud_id: str,
    site_url: str | None,
    site_name: str | None,
    workspace_id: str,
    access_token: str,
    refresh_token: str | None,
    installed_by: str | None,
) -> dict:
    """Record or refresh a Jira installation.

    Conflict is on cloud_id because a Jira Cloud site should have one active
    installation record. Reconnecting the same site replaces its tokens.
    """

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jira_installations
                (
                    cloud_id,
                    site_url,
                    site_name,
                    workspace_id,
                    access_token,
                    refresh_token,
                    installed_by
                )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cloud_id) DO UPDATE
                SET site_url       = excluded.site_url,
                    site_name      = excluded.site_name,
                    workspace_id   = excluded.workspace_id,
                    access_token   = excluded.access_token,
                    refresh_token  = excluded.refresh_token,
                    installed_by   = excluded.installed_by,
                    installed_at   = now()
            RETURNING
                id,
                cloud_id,
                site_url,
                site_name,
                workspace_id,
                installed_at;
            """,
            (
                cloud_id,
                site_url,
                site_name,
                workspace_id,
                access_token,
                refresh_token,
                installed_by,
            ),
        )

        return cur.fetchone()


def get_installation_by_cloud_id(
    cloud_id: str,
) -> dict | None:
    """Resolve a Jira Cloud site ID to its installation."""

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                cloud_id,
                site_url,
                site_name,
                workspace_id,
                access_token,
                refresh_token,
                installed_at
            FROM jira_installations
            WHERE cloud_id = %s;
            """,
            (cloud_id,),
        )

        return cur.fetchone()


def get_installation_by_workspace(
    workspace_id: str,
) -> dict | None:
    """Return the Jira installation connected to this application workspace."""

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                cloud_id,
                site_url,
                site_name,
                workspace_id,
                access_token,
                refresh_token,
                installed_at
            FROM jira_installations
            WHERE workspace_id = %s
            ORDER BY installed_at DESC
            LIMIT 1;
            """,
            (workspace_id,),
        )

        return cur.fetchone()


def delete_installation(
    workspace_id: str,
) -> bool:
    """Remove Jira credentials for a workspace.

    Existing source events and memories are intentionally preserved.
    """

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM jira_installations
            WHERE workspace_id = %s;
            """,
            (workspace_id,),
        )

        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Raw source events
# ---------------------------------------------------------------------------

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
    """Claim a Jira issue for processing.

    Uses the shared source_events table.

    external_id makes ingestion idempotent:
        jira:{cloud_id}:{issue_key}

    If the same issue has already been recorded, returns None.
    """

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_events
                (
                    workspace_id,
                    source,
                    external_id,
                    author,
                    text,
                    occurred_at,
                    payload
                )
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
    reason: str | None = None,
    memory_id: str | None = None,
) -> None:
    """Mark a Jira source event as successfully processed or failed."""

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE source_events
            SET
                outcome = %s,
                reason = %s,
                memory_id = %s,
                processed_at = now()
            WHERE id = %s;
            """,
            (
                outcome,
                reason,
                memory_id,
                event_id,
            ),
        )


def recent_source_events(
    workspace_id: str,
    limit: int = 25,
) -> list[dict]:
    """Return recent Jira ingestion activity for the Sources page."""

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                e.id,
                e.source,
                e.external_id,
                e.author,
                e.text,
                e.occurred_at,
                e.outcome,
                e.reason,
                e.memory_id,
                e.received_at,
                m.title AS memory_title,
                m.type AS memory_type
            FROM source_events e
            LEFT JOIN memories m
                ON m.id = e.memory_id
            WHERE
                e.workspace_id = %s
                AND e.source = 'jira'
            ORDER BY e.received_at DESC
            LIMIT %s;
            """,
            (
                workspace_id,
                limit,
            ),
        )

        return cur.fetchall()


def source_event_stats(
    workspace_id: str,
    source: str = "jira",
) -> dict:
    """Return Jira ingestion counts for the Sources page."""

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                count(*) AS received,
                count(*) FILTER (
                    WHERE outcome = 'stored'
                ) AS stored,
                count(*) FILTER (
                    WHERE outcome = 'quarantined'
                ) AS quarantined,
                count(*) FILTER (
                    WHERE outcome LIKE 'dropped%%'
                ) AS dropped,
                count(*) FILTER (
                    WHERE outcome IN ('pending', 'error')
                ) AS unfinished,
                max(received_at) AS last_event_at
            FROM source_events
            WHERE
                workspace_id = %s
                AND source = %s;
            """,
            (
                workspace_id,
                source,
            ),
        )

        return cur.fetchone()