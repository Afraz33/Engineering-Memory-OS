"""Thin Atlassian (Jira Cloud) client.

Same shape as `services.slack_client` — only the calls the connector needs, on
raw httpx rather than the official SDK. Three things differ from Slack and each
one shapes this file:

1. **Tokens expire.** Slack's `xoxb-` token is good until revoked; a Jira 3LO
   access token lasts an hour. So every install carries a refresh token, and
   `refresh_access_token` is on the hot path rather than a rainy-day function.
   Atlassian *rotates* the refresh token on each use, so the new one must be
   persisted or the install dies at the next refresh.

2. **The site id is the routing key.** There is no per-request "which Jira is
   this" field like Slack's `team_id`; the cloud id is in the URL itself
   (`api.atlassian.com/ex/jira/{cloud_id}/...`), which is why the install flow
   has an extra `accessible_resources` round trip to learn it.

3. **Text arrives as a document, not a string.** REST v3 returns descriptions
   and comments in Atlassian Document Format — a nested JSON tree. `adf_to_text`
   flattens it, because the classifier reads prose and the pre-filter measures
   length in characters of prose.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

AUTH_BASE = "https://auth.atlassian.com"
API_BASE = "https://api.atlassian.com"

TIMEOUT = httpx.Timeout(20.0)

# Read work + users to classify an issue; manage webhooks to subscribe without
# the user hand-configuring one; offline_access is what mints a refresh token
# at all. Adding a scope later forces every site to reconnect, so this list is
# deliberately complete.
SCOPES = (
    "read:jira-work",
    "read:jira-user",
    "manage:jira-webhook",
    "offline_access",
)

# Events we subscribe to. Deliberately not `jira:issue_deleted` or worklog
# noise: capture is about what was decided, and a deletion carries no claim.
WEBHOOK_EVENTS = (
    "jira:issue_created",
    "jira:issue_updated",
    "comment_created",
    "comment_updated",
)

# Atlassian expires a dynamic webhook 30 days after registration. Refresh well
# before that so a quiet workspace doesn't wake up unsubscribed.
WEBHOOK_TTL_DAYS = 30
WEBHOOK_REFRESH_AFTER_DAYS = 20

# Ask for a new access token slightly before it actually expires, so a call
# that starts near the boundary doesn't land after it.
TOKEN_EXPIRY_SKEW = timedelta(seconds=60)


class JiraError(RuntimeError):
    """Jira rejected the call."""


@dataclass(slots=True)
class Tokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scopes: str | None


@dataclass(slots=True)
class Site:
    """One Atlassian site the user granted us access to."""

    cloud_id: str
    name: str | None
    url: str | None


# --- config -----------------------------------------------------------------
# Read at call time, not import time — `app.main` imports the router before it
# calls load_dotenv().


def client_id() -> str:
    return os.getenv("JIRA_CLIENT_ID", "")


def client_secret() -> str:
    return os.getenv("JIRA_CLIENT_SECRET", "")


def is_configured() -> bool:
    return bool(client_id() and client_secret())


def api_url(cloud_id: str, path: str) -> str:
    return f"{API_BASE}/ex/jira/{cloud_id}/rest/api/3/{path.lstrip('/')}"


# --- OAuth ------------------------------------------------------------------


def _tokens_from(body: dict) -> Tokens:
    return Tokens(
        access_token=body.get("access_token", ""),
        refresh_token=body.get("refresh_token"),
        expires_at=datetime.now(UTC) + timedelta(seconds=int(body.get("expires_in", 3600))),
        scopes=body.get("scope"),
    )


async def _token_call(payload: dict) -> Tokens:
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        resp = await http.post(f"{AUTH_BASE}/oauth/token", json=payload)
    if resp.status_code >= 400:
        raise JiraError(f"oauth/token: {resp.status_code} {resp.text[:200]}")
    return _tokens_from(resp.json())


async def exchange_code(code: str, redirect_uri: str) -> Tokens:
    """Turn the one-time `code` from the OAuth redirect into tokens."""
    return await _token_call(
        {
            "grant_type": "authorization_code",
            "client_id": client_id(),
            "client_secret": client_secret(),
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )


async def refresh_access_token(refresh_token: str) -> Tokens:
    """Trade the refresh token for a new access token — and a new refresh
    token, which the caller must store. Atlassian invalidates the old one."""
    return await _token_call(
        {
            "grant_type": "refresh_token",
            "client_id": client_id(),
            "client_secret": client_secret(),
            "refresh_token": refresh_token,
        }
    )


async def accessible_resources(access_token: str) -> list[Site]:
    """Which sites the grant actually covers.

    The consent screen lets the user pick one site out of several, and the
    token says nothing about which — this is the only way to learn the cloud id
    every later call needs.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        resp = await http.get(
            f"{API_BASE}/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code >= 400:
        raise JiraError(f"accessible-resources: {resp.status_code} {resp.text[:200]}")
    return [
        Site(cloud_id=r.get("id", ""), name=r.get("name"), url=r.get("url"))
        for r in resp.json()
    ]


# --- REST -------------------------------------------------------------------


async def _call(
    method: str,
    cloud_id: str,
    token: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        resp = await http.request(
            method,
            api_url(cloud_id, path),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            params=params,
            json=json_body,
        )
    if resp.status_code >= 400:
        raise JiraError(f"{method} {path}: {resp.status_code} {resp.text[:200]}")
    if not resp.content:
        return {}
    return resp.json()


async def get_issue(cloud_id: str, token: str, issue_key: str) -> dict:
    """Full issue. The webhook payload already carries most of this, but a
    backfill and a comment event do not."""
    return await _call(
        "GET",
        cloud_id,
        token,
        f"issue/{issue_key}",
        params={"fields": "summary,description,issuetype,status,project,reporter,created,updated"},
    )


async def search_issues(
    cloud_id: str, token: str, jql: str, limit: int = 50
) -> list[dict]:
    """Run a JQL query — the backfill path.

    Webhooks only cover what happens *after* connecting, and the interesting
    decisions are usually already in the backlog. `/search/jql` is the current
    endpoint; the older `/search` is kept as a fallback because sites on an
    older API version still answer there and returning nothing would look
    exactly like "no matching issues".
    """
    params = {
        "jql": jql,
        "maxResults": limit,
        "fields": "summary,description,issuetype,status,project,reporter,created,updated",
    }
    try:
        body = await _call("GET", cloud_id, token, "search/jql", params=params)
    except JiraError:
        body = await _call("GET", cloud_id, token, "search", params=params)
    return body.get("issues") or []


async def myself(cloud_id: str, token: str) -> dict:
    return await _call("GET", cloud_id, token, "myself")


# --- webhooks ---------------------------------------------------------------


async def register_webhook(
    cloud_id: str, token: str, url: str, jql: str = "project is not EMPTY"
) -> str | None:
    """Subscribe to issue and comment events. Returns the webhook id.

    `jqlFilter` is required by the API and is also the first of the criteria
    that decide what reaches the pipeline at all — everything Jira filters out
    here is a webhook delivery, an audit row, and an LLM call we never pay for.

    Returns None (rather than raising) when Atlassian refuses the registration:
    dynamic webhooks require the URL to sit under the app's configured base URL
    in the developer console, and a mismatch there should degrade to "configure
    it by hand", not to a failed install.
    """
    try:
        body = await _call(
            "POST",
            cloud_id,
            token,
            "webhook",
            json_body={
                "url": url,
                "webhooks": [{"events": list(WEBHOOK_EVENTS), "jqlFilter": jql}],
            },
        )
    except (JiraError, httpx.HTTPError):
        return None

    results = body.get("webhookRegistrationResult") or []
    for entry in results:
        if entry.get("createdWebhookId"):
            return str(entry["createdWebhookId"])
    return None


async def refresh_webhook(cloud_id: str, token: str, webhook_id: str) -> bool:
    """Push the expiry out another 30 days. Called from the status poll, which
    is the only thing guaranteed to run while a workspace is in use."""
    try:
        await _call(
            "PUT",
            cloud_id,
            token,
            "webhook/refresh",
            json_body={"webhookIds": [int(webhook_id)]},
        )
        return True
    except (JiraError, httpx.HTTPError, ValueError):
        return False


async def delete_webhook(cloud_id: str, token: str, webhook_id: str) -> bool:
    """Unsubscribe on disconnect. Best-effort: if this fails the deliveries
    keep arriving, but the receiver no longer resolves them to an install and
    drops them."""
    try:
        await _call(
            "DELETE",
            cloud_id,
            token,
            "webhook",
            json_body={"webhookIds": [int(webhook_id)]},
        )
        return True
    except (JiraError, httpx.HTTPError, ValueError):
        return False


# --- Atlassian Document Format ----------------------------------------------

# Node types that occupy a line of their own. Without these, a bulleted list of
# constraints flattens into one run-on sentence and the classifier reads it as
# a single claim.
_BLOCK_NODES = {
    "paragraph",
    "heading",
    "listItem",
    "blockquote",
    "codeBlock",
    "panel",
    "rule",
    "tableRow",
    "bulletList",
    "orderedList",
    "table",
    "mediaSingle",
}


def adf_to_text(node: Any) -> str:
    """Flatten an Atlassian Document Format tree to plain text.

    REST v3 returns rich text as nested JSON. Anything that is already a string
    (v2 sites, webhook payloads with `renderedFields`) passes straight through.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node.strip()
    if isinstance(node, list):
        return "\n".join(part for part in (adf_to_text(n) for n in node) if part)
    if not isinstance(node, dict):
        return ""

    kind = node.get("type")

    if kind == "text":
        return node.get("text", "")
    # Mentions and emoji carry no text node of their own; the label is the only
    # readable trace of who was named.
    if kind == "mention":
        return (node.get("attrs") or {}).get("text", "")
    if kind == "emoji":
        return (node.get("attrs") or {}).get("text", "")
    if kind == "inlineCard":
        return (node.get("attrs") or {}).get("url", "")
    if kind == "hardBreak":
        return "\n"

    inner = node.get("content")
    if not inner:
        return ""

    parts = [part for part in (adf_to_text(n) for n in inner) if part]

    # A node whose children are blocks (a doc of paragraphs, a list of items)
    # joins them with newlines; a node whose children are inline runs (a
    # paragraph of styled text) joins them with nothing, or every bold word
    # would land on its own line.
    children_are_blocks = any(
        isinstance(n, dict) and n.get("type") in _BLOCK_NODES for n in inner
    )
    return ("\n" if children_are_blocks else "").join(parts)


def issue_url(site_url: str | None, issue_key: str) -> str | None:
    """The provenance link. Without it a memory cannot be traced back to the
    issue it came from, which Scope §6 treats as non-negotiable."""
    if not site_url or not issue_key:
        return None
    return f"{site_url.rstrip('/')}/browse/{issue_key}"
