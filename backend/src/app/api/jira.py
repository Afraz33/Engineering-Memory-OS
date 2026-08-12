"""The Jira connector.

Surfaces:

    GET  /api/jira/install       browser, cookie-authenticated -> authorize URL
    GET  /api/jira/callback      browser, state-authenticated  -> stores token
    GET  /api/jira/status        browser, cookie-authenticated -> connection status
    DELETE /api/jira/disconnect  browser, cookie-authenticated -> removes token
    POST /api/jira/sync          browser, cookie-authenticated -> pulls Jira issues
    GET  /api/jira/activity      browser, cookie-authenticated -> ingestion audit feed

Jira is initially pull-based. The sync endpoint fetches issues using JQL,
records them as source events, and processes them through the existing
normalization/ingestion pipeline.

Later, Jira webhooks can be added without changing the rest of the pipeline.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.auth import UserOut, current_user
from ai.ingest import ClassificationError, ingest, normalize
from ai.ingest.events.events import JiraEventIn, JiraPayload
from ai.memory import get_store
from ai.providers.llm import ProviderError, get_provider
from db import jira as jira_db
from services import jira_client

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jira", tags=["jira"])

STATE_TTL = timedelta(minutes=10)


# --- Config ----------------------------------------------------------------

def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def _redirect_uri() -> str:
    """
    Must exactly match the callback URL registered in the Atlassian app.
    """
    return f"{_backend_url()}/api/jira/callback"


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "")


def workspace_id_for(user: UserOut) -> str:
    """
    Same tenancy model as Slack for now.

    When real teams/workspaces are introduced, this is the function
    that should change.
    """
    return user.id


# --- Response models -------------------------------------------------------

class InstallUrlOut(BaseModel):
    url: str


class JiraStatusOut(BaseModel):
    configured: bool
    connected: bool
    site_name: str | None = None
    site_url: str | None = None
    cloud_id: str | None = None
    installed_at: datetime | None = None

    received: int = 0
    stored: int = 0
    quarantined: int = 0
    dropped: int = 0
    errors: int = 0

    last_event_at: datetime | None = None


class JiraSyncIn(BaseModel):
    """
    Controls what Jira issues should be pulled.

    Example:
        project = ENG ORDER BY updated DESC
    """

    jql: str = "ORDER BY updated DESC"
    max_results: int = 100


class JiraSyncOut(BaseModel):
    fetched: int
    recorded: int
    skipped: int


class SourceEventOut(BaseModel):
    id: str
    author: str | None
    text: str | None
    outcome: str
    reason: str | None
    occurred_at: datetime | None
    memory_id: str | None
    memory_title: str | None
    memory_type: str | None


# --- Install flow ----------------------------------------------------------

@router.get("/install", response_model=InstallUrlOut)
async def install_url(
    user: UserOut = Depends(current_user),
) -> InstallUrlOut:
    """
    Build the Atlassian OAuth authorization URL.

    The frontend sends the user here to connect their Jira account/site.
    """

    if not jira_client.is_configured():
        raise HTTPException(
            503,
            "Jira is not configured: set JIRA_CLIENT_ID and "
            "JIRA_CLIENT_SECRET in backend/.env",
        )

    now = datetime.now(UTC)

    state = jwt.encode(
        {
            "uid": user.id,
            "purpose": "jira_install",
            "iat": now,
            "exp": now + STATE_TTL,
        },
        _jwt_secret(),
        algorithm="HS256",
    )

    # These scopes should match the scopes configured in the Atlassian app.
    scopes = [
        "read:jira-work",
        "read:jira-user",
        "offline_access",
    ]

    query = urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": jira_client.client_id(),
            "scope": " ".join(scopes),
            "redirect_uri": _redirect_uri(),
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
    )

    return InstallUrlOut(
        url=f"https://auth.atlassian.com/authorize?{query}"
    )


@router.get("/callback")
async def install_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """
    Atlassian redirects here after the user approves or rejects the install.
    """

    if error or not code or not state:
        return RedirectResponse(
            f"{_frontend_url()}/sources"
            f"?jira=error&reason={error or 'cancelled'}"
        )

    try:
        claims = jwt.decode(
            state,
            _jwt_secret(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return RedirectResponse(
            f"{_frontend_url()}/sources?jira=error&reason=bad_state"
        )

    if claims.get("purpose") != "jira_install":
        return RedirectResponse(
            f"{_frontend_url()}/sources?jira=error&reason=bad_state"
        )

    try:
        installation = await jira_client.exchange_code(
            code,
            _redirect_uri(),
        )

    except (jira_client.JiraError, httpx.HTTPError) as exc:
        log.warning("jira oauth exchange failed: %s", exc)

        return RedirectResponse(
            f"{_frontend_url()}/sources"
            "?jira=error&reason=exchange"
        )

    await asyncio.to_thread(
        jira_db.upsert_installation,
        cloud_id=installation.cloud_id,
        site_url=installation.site_url,
        site_name=installation.site_name,
        workspace_id=claims["uid"],
        access_token=installation.access_token,
        refresh_token=installation.refresh_token,
        installed_by=claims["uid"],
    )

    return RedirectResponse(
        f"{_frontend_url()}/sources?jira=connected"
    )


# --- Status ----------------------------------------------------------------

@router.get("/status", response_model=JiraStatusOut)
async def status(
    user: UserOut = Depends(current_user),
) -> JiraStatusOut:
    """
    Return Jira connection and ingestion status.
    """

    workspace_id = workspace_id_for(user)

    installation = await asyncio.to_thread(
        jira_db.get_installation_by_workspace,
        workspace_id,
    )

    stats = await asyncio.to_thread(
        jira_db.source_event_stats,
        workspace_id,
        "jira",
    )

    return JiraStatusOut(
        configured=jira_client.is_configured(),
        connected=installation is not None,
        site_name=(
            installation["site_name"]
            if installation
            else None
        ),
        site_url=(
            installation["site_url"]
            if installation
            else None
        ),
        cloud_id=(
            installation["cloud_id"]
            if installation
            else None
        ),
        installed_at=(
            installation["installed_at"]
            if installation
            else None
        ),
        received=stats["received"] or 0,
        stored=stats["stored"] or 0,
        quarantined=stats["quarantined"] or 0,
        dropped=stats["dropped"] or 0,
        errors=stats.get("errors", 0) or 0,
        last_event_at=stats["last_event_at"],
    )


# --- Disconnect ------------------------------------------------------------

@router.delete("/disconnect")
async def disconnect(
    user: UserOut = Depends(current_user),
) -> dict[str, bool]:
    """
    Remove the Jira OAuth credentials.

    Existing memories are intentionally retained.
    """

    removed = await asyncio.to_thread(
        jira_db.delete_installation,
        workspace_id_for(user),
    )

    return {"ok": removed}


# --- Activity --------------------------------------------------------------

@router.get(
    "/activity",
    response_model=list[SourceEventOut],
)
async def activity(
    limit: int = 25,
    user: UserOut = Depends(current_user),
) -> list[SourceEventOut]:
    """
    Show recent Jira ingestion activity.

    This makes failed/skipped/processed Jira tickets debuggable.
    """

    rows = await asyncio.to_thread(
        jira_db.recent_source_events,
        workspace_id_for(user),
        min(limit, 100),
    )

    return [
        SourceEventOut(
            id=str(row["id"]),
            author=row["author"],
            text=row["text"],
            outcome=row["outcome"],
            reason=row["reason"],
            occurred_at=row["occurred_at"],
            memory_id=(
                str(row["memory_id"])
                if row["memory_id"]
                else None
            ),
            memory_title=row["memory_title"],
            memory_type=row["memory_type"],
        )
        for row in rows
    ]


# --- Sync ------------------------------------------------------------------

@router.post("/sync", response_model=JiraSyncOut)
async def sync(
    payload: JiraSyncIn,
    tasks: BackgroundTasks,
    user: UserOut = Depends(current_user),
) -> JiraSyncOut:
    """
    Pull Jira issues and queue them for ingestion.

    Example JQL:

        project = ENG ORDER BY updated DESC

    The issues are recorded first so repeated syncs can be made idempotent.
    """

    workspace_id = workspace_id_for(user)

    installation = await asyncio.to_thread(
        jira_db.get_installation_by_workspace,
        workspace_id,
    )

    if installation is None:
        raise HTTPException(
            400,
            "Jira is not connected.",
        )

    max_results = min(max(payload.max_results, 1), 100)

    try:
        result = await jira_client.list_issues(
            token=installation["access_token"],
            cloud_id=installation["cloud_id"],
            jql=payload.jql,
            start_at=0,
            max_results=max_results,
        )
    except (jira_client.JiraError, httpx.HTTPError) as exc:
        log.warning(
            "jira sync failed for workspace %s: %s",
            workspace_id,
            exc,
        )
        raise HTTPException(
            502,
            "Could not fetch issues from Jira.",
        ) from exc

    issues = result.get("issues", [])

    recorded = 0
    skipped = 0

    for issue in issues:
        issue_key = issue.get("key")

        if not issue_key:
            skipped += 1
            continue

        fields = issue.get("fields") or {}

        external_id = (
            f"jira:{installation['cloud_id']}:"
            f"{issue_key}:{fields.get('updated', '')}"
        )

        occurred_at = _from_jira_timestamp(
            fields.get("updated") or fields.get("created")
        )

        row_id = await asyncio.to_thread(
            jira_db.record_source_event,
            workspace_id=workspace_id,
            source="jira",
            external_id=external_id,
            author=_author_name(fields),
            text=_issue_text(issue),
            occurred_at=occurred_at,
            payload=issue,
        )

        if row_id is None:
            skipped += 1
            continue

        recorded += 1

        tasks.add_task(
            process_issue,
            row_id,
            dict(installation),
            issue,
        )

    return JiraSyncOut(
        fetched=len(issues),
        recorded=recorded,
        skipped=skipped,
    )


# --- Issue processing -----------------------------------------------------------

async def process_issue(
    row_id: str,
    installation: dict,
    issue: dict,
) -> None:
    """
    Convert one Jira issue into the existing ingestion pipeline.

    This is intentionally separate from the Jira client:
        Jira API -> JiraPayload -> normalize() -> ingest()
    """

    try:
        fields = issue.get("fields") or {}

        issue_key = issue.get("key", "")
        summary = fields.get("summary") or ""
        description = _description_text(
            fields.get("description")
        )

        project = fields.get("project") or {}
        issue_type = fields.get("issuetype") or {}
        status = fields.get("status") or {}
        priority = fields.get("priority") or {}

        payload = JiraPayload(
            issue_id=str(issue.get("id", "")),
            issue_key=issue_key,
            summary=summary,
            description=description,
            project_id=project.get("id"),
            project_key=project.get("key"),
            project_name=project.get("name"),
            issue_type=issue_type.get("name"),
            status=status.get("name"),
            priority=priority.get("name"),
            labels=fields.get("labels") or [],
            components=[
                component.get("name")
                for component in fields.get("components") or []
                if component.get("name")
            ],
            reporter=_user_display_name(
                fields.get("reporter")
            ),
            assignee=_user_display_name(
                fields.get("assignee")
            ),
            created_at=fields.get("created"),
            updated_at=fields.get("updated"),
            url=jira_client.issue_url(
                installation["site_url"],
                issue_key,
            ),
        )

        request = JiraEventIn(
            source="jira",
            workspace_id=installation["workspace_id"],
            payload=payload,
        )

        result = await ingest(
            normalize(request),
            workspace_id=installation["workspace_id"],
            provider=get_provider(),
            store=get_store(),
        )

        await asyncio.to_thread(
            jira_db.finish_source_event,
            row_id,
            outcome=result.outcome,
            reason=result.reason,
            memory_id=(
                result.memory.id
                if result.memory
                else None
            ),
        )

    except (ClassificationError, ProviderError) as exc:
        log.warning(
            "jira ingest failed for %s: %s",
            row_id,
            exc,
        )

        await asyncio.to_thread(
            jira_db.finish_source_event,
            row_id,
            outcome="error",
            reason=str(exc),
        )

    except Exception as exc:
        log.exception(
            "jira ingest crashed for %s",
            row_id,
        )

        await asyncio.to_thread(
            jira_db.finish_source_event,
            row_id,
            outcome="error",
            reason=str(exc),
        )


# --- Jira helpers -------------------------------------------------------

def _from_jira_timestamp(
    value: str | None,
) -> datetime:
    """
    Convert Jira's ISO timestamp into a timezone-aware datetime.
    """

    if not value:
        return datetime.now(UTC)

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return datetime.now(UTC)


def _user_display_name(
    user: dict | None,
) -> str | None:
    """
    Extract a human-readable Jira user name.
    """

    if not user:
        return None

    return (
        user.get("displayName")
        or user.get("emailAddress")
        or user.get("accountId")
    )


def _author_name(
    fields: dict,
) -> str | None:
    """
    Get the issue reporter for the source-event audit record.
    """

    return _user_display_name(
        fields.get("reporter")
    )


def _issue_text(
    issue: dict,
) -> str:
    """
    Create the short source-event text shown in the activity feed.
    """

    fields = issue.get("fields") or {}

    summary = fields.get("summary") or ""
    description = _description_text(
        fields.get("description")
    )

    if description:
        return f"{summary}\n\n{description}"

    return summary


def _description_text(
    description: object,
) -> str:
    """
    Convert Jira's description representation into plain text.

    Jira Cloud commonly returns Atlassian Document Format (ADF), so this
    should eventually be replaced by a proper ADF -> text converter.
    """

    if not description:
        return ""

    if isinstance(description, str):
        return description

    if not isinstance(description, dict):
        return str(description)

    parts: list[str] = []

    def walk(node: object) -> None:
        if not isinstance(node, dict):
            return

        text = node.get("text")
        if isinstance(text, str):
            parts.append(text)

        for child in node.get("content") or []:
            walk(child)

        if node.get("type") in {
            "paragraph",
            "heading",
            "blockquote",
            "listItem",
        }:
            parts.append("\n")

    walk(description)

    return "".join(parts).strip()