"""Queries for the Jira connector: installations.

The raw-event side is shared with Slack — see `db.source_events`, re-exported
below so the router reads `jira_db.record_source_event` the same way the Slack
one does.

All functions here are blocking (the pool is sync). Callers on the event loop
must wrap them in `asyncio.to_thread`; the webhook handler does.
"""

from typing import Any

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
    "get_installation_by_cloud_id",
    "get_installation_by_secret",
    "get_installation_by_workspace",
    "mark_synced",
    "recent_source_events",
    "record_source_event",
    "source_event_stats",
    "update_tokens",
    "update_webhook",
    "upsert_installation",
]

# Every column except the two secrets. The status endpoint and the UI have no
# use for tokens, and not selecting them is cheaper than remembering to strip
# them at each call site.
_PUBLIC_COLUMNS = """
    id, cloud_id, site_name, site_url, workspace_id, scopes,
    webhook_id, webhook_registered_at, last_synced_at, installed_at
"""


def upsert_installation(
    *,
    cloud_id: str,
    site_name: str | None,
    site_url: str | None,
    workspace_id: str,
    access_token: str,
    refresh_token: str | None,
    expires_at: Any,
    scopes: str | None,
    webhook_secret: str,
    installed_by: str | None,
) -> dict:
    """Record (or refresh) a connection.

    Conflict is on `cloud_id`: reconnecting the same Atlassian site issues new
    tokens and must replace the old row, not add a second one the webhook
    receiver would then have to choose between.

    `webhook_secret` is only written on first insert — rotating it on every
    reconnect would silently orphan a webhook that is still registered with the
    old URL.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jira_installations
                (cloud_id, site_name, site_url, workspace_id, access_token,
                 refresh_token, expires_at, scopes, webhook_secret, installed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cloud_id) DO UPDATE
                SET site_name     = excluded.site_name,
                    site_url      = excluded.site_url,
                    workspace_id  = excluded.workspace_id,
                    access_token  = excluded.access_token,
                    refresh_token = excluded.refresh_token,
                    expires_at    = excluded.expires_at,
                    scopes        = excluded.scopes,
                    installed_by  = excluded.installed_by,
                    installed_at  = now()
            RETURNING id, cloud_id, site_name, site_url, workspace_id,
                      webhook_id, webhook_secret, installed_at;
            """,
            (
                cloud_id,
                site_name,
                site_url,
                workspace_id,
                access_token,
                refresh_token,
                expires_at,
                scopes,
                webhook_secret,
                installed_by,
            ),
        )
        return cur.fetchone()


def get_installation_by_workspace(workspace_id: str) -> dict | None:
    """What the UI asks: is this workspace connected, and to which site?

    Returns tokens too — the status poll refreshes the webhook registration,
    which needs one.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_PUBLIC_COLUMNS}, access_token, refresh_token, expires_at,
                   webhook_secret
            FROM jira_installations
            WHERE workspace_id = %s
            ORDER BY installed_at DESC
            LIMIT 1;
            """,
            (workspace_id,),
        )
        return cur.fetchone()


def get_installation_by_cloud_id(cloud_id: str) -> dict | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_PUBLIC_COLUMNS}, access_token, refresh_token, expires_at,
                   webhook_secret
            FROM jira_installations
            WHERE cloud_id = %s;
            """,
            (cloud_id,),
        )
        return cur.fetchone()


def get_installation_by_secret(webhook_secret: str) -> dict | None:
    """Resolve an inbound webhook to a tenant.

    Jira does not sign deliveries for OAuth apps, so possession of this secret
    *is* the authentication — which is why it is a unique column and the lookup
    is exact-match rather than anything cleverer.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_PUBLIC_COLUMNS}, access_token, refresh_token, expires_at
            FROM jira_installations
            WHERE webhook_secret = %s;
            """,
            (webhook_secret,),
        )
        return cur.fetchone()


def update_tokens(
    installation_id: str,
    *,
    access_token: str,
    refresh_token: str | None,
    expires_at: Any,
) -> None:
    """Persist a rotated token pair.

    Atlassian invalidates the old refresh token the moment it issues a new one,
    so skipping this write breaks the install an hour later, not immediately —
    the worst kind of failure to debug. COALESCE guards the case where a
    response omits the refresh token: keep the one we have rather than nulling
    the only way back.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jira_installations
            SET access_token  = %s,
                refresh_token = COALESCE(%s, refresh_token),
                expires_at    = %s
            WHERE id = %s;
            """,
            (access_token, refresh_token, expires_at, installation_id),
        )


def update_webhook(installation_id: str, webhook_id: str | None) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jira_installations
            SET webhook_id = %s, webhook_registered_at = now()
            WHERE id = %s;
            """,
            (webhook_id, installation_id),
        )


def mark_synced(installation_id: str) -> None:
    """High-water mark for the backfill, so a re-sync only pulls issues touched
    since the last one."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE jira_installations SET last_synced_at = now() WHERE id = %s;",
            (installation_id,),
        )


def delete_installation(workspace_id: str) -> bool:
    """Forget the tokens. Captured memories stay — they are the product."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM jira_installations WHERE workspace_id = %s;",
            (workspace_id,),
        )
        return cur.rowcount > 0
