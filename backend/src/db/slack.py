"""Queries for the Slack connector: installations.

Kept out of `db/models.py` because this table belongs to the connector, not to
the memory domain — the rest of the app never reads it.

The raw-event queries used to live here too. They moved to `db.source_events`
once Jira needed the same four functions verbatim; they are re-exported below
so `slack_db.record_source_event` still reads naturally at the call sites in
`app.api.slack`.

All functions here are blocking (the pool is sync). Callers on the event loop
must wrap them in `asyncio.to_thread`; the webhook handler does.
"""

from db.session import get_conn
from db.source_events import (
    finish_source_event,
    record_source_event,
    recent_source_events,
    source_event_stats,
)

__all__ = [
    "delete_installation",
    "finish_source_event",
    "get_installation_by_team",
    "get_installation_by_workspace",
    "recent_source_events",
    "record_source_event",
    "source_event_stats",
    "upsert_installation",
]

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
