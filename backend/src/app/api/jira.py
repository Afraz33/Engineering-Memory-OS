"""The Jira connector.

Six surfaces, and like Slack they have different trust models — which is why
this is its own router rather than more routes on `/api/events`:

    GET    /api/jira/install          browser, cookie-authenticated  → authorize URL
    GET    /api/jira/callback         browser, `state`-authenticated → stores tokens
    GET    /api/jira/status           browser, cookie-authenticated
    GET    /api/jira/activity         browser, cookie-authenticated
    DELETE /api/jira/disconnect       browser, cookie-authenticated
    POST   /api/jira/sync             browser, cookie-authenticated  → JQL backfill
    POST   /api/jira/webhook/{secret} Jira,    secret-authenticated

Two things differ from the Slack connector and both shape this file.

**Authentication.** Slack signs every delivery with a shared secret over the
raw bytes. Jira does not sign webhooks for OAuth (3LO) apps at all, so the
secret goes in the callback path and possession of it is the authentication.
That is weaker than an HMAC — the URL is a bearer credential — so it is
per-installation, high-entropy, and revoked by disconnecting. See
docs/jira-integration.md.

**Tokens expire.** Every outbound call goes through `_token`, which refreshes
and persists before handing back an access token. Atlassian rotates the refresh
token on use, so a dropped write here breaks the install an hour later.

The webhook still records-then-acks like Slack's: Jira retries deliveries it
thinks failed, so `record_source_event` is what makes a retry idempotent.
"""

import asyncio
import logging
import os
import secrets
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
from db import workspaces as workspaces_db
from services import jira_client

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jira", tags=["jira"])

STATE_TTL = timedelta(minutes=10)

# How many issues one backfill pass pulls. Bounded because every issue that
# survives the pre-filter costs an LLM call, and a first sync against a
# ten-year-old project would otherwise bill for all of it at once.
SYNC_LIMIT = 50

# Only issues touched in this window are worth backfilling: older ones are
# either already captured or no longer describe how the system works.
SYNC_LOOKBACK_DAYS = 90


# --- config -----------------------------------------------------------------
# Read at call time, not import time: `app.main` imports this router before it
# calls load_dotenv(), so module-level reads would see an empty environment.


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def _redirect_uri() -> str:
    """Must byte-for-byte match the callback URL registered in the Atlassian
    developer console, and must be sent again on the token exchange."""
    return f"{_backend_url()}/api/jira/callback"


def _webhook_url(secret: str) -> str:
    return f"{_backend_url()}/api/jira/webhook/{secret}"


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "")


async def workspace_for(user: UserOut) -> dict:
    """Resolve the caller's *active* workspace (id, name, role)."""
    return await asyncio.to_thread(workspaces_db.get_workspace_for_user, user.id)


async def _token(install: dict) -> str:
    """A usable access token, refreshing and persisting it if it has expired.

    Every outbound Jira call goes through here. The write-back is not optional:
    Atlassian invalidates the old refresh token the moment it issues a new one.
    """
    expires_at = install.get("expires_at")
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at and datetime.now(UTC) + jira_client.TOKEN_EXPIRY_SKEW < expires_at:
        return install["access_token"]

    refresh = install.get("refresh_token")
    if not refresh:
        # No offline_access on the original grant, or a row from before it was
        # requested. Nothing to do but reconnect.
        raise jira_client.JiraError("no refresh token; reconnect Jira")

    tokens = await jira_client.refresh_access_token(refresh)
    await asyncio.to_thread(
        jira_db.update_tokens,
        str(install["id"]),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_at=tokens.expires_at,
    )
    # Keep the caller's dict usable — it is passed on to background tasks.
    install["access_token"] = tokens.access_token
    install["refresh_token"] = tokens.refresh_token or refresh
    install["expires_at"] = tokens.expires_at
    return tokens.access_token


# --- install flow -----------------------------------------------------------


class InstallUrlOut(BaseModel):
    url: str


class JiraStatusOut(BaseModel):
    configured: bool  # server has Atlassian credentials at all
    connected: bool
    site_name: str | None = None
    site_url: str | None = None
    installed_at: datetime | None = None
    last_synced_at: datetime | None = None
    # False means the dynamic registration was refused and the user has to add
    # a webhook by hand — the UI shows `webhook_url` for exactly that case.
    webhook_active: bool = False
    webhook_url: str | None = None
    received: int = 0
    stored: int = 0
    quarantined: int = 0
    dropped: int = 0
    last_event_at: datetime | None = None


@router.get("/install", response_model=InstallUrlOut)
async def install_url(user: UserOut = Depends(current_user)) -> InstallUrlOut:
    """Where to send the browser to start the connection."""
    if not jira_client.is_configured():
        raise HTTPException(
            503,
            "Jira is not configured: set JIRA_CLIENT_ID and JIRA_CLIENT_SECRET "
            "in backend/.env",
        )

    workspace = await workspace_for(user)
    if workspace["role"] != "owner":
        raise HTTPException(403, "only the workspace owner can connect Jira")

    # Same reasoning as the Slack connector: a signed, short-lived `state`
    # survives the round trip through Atlassian, proves the callback belongs to
    # this user, and needs no server-side storage to verify.
    now = datetime.now(UTC)
    state = jwt.encode(
        {
            "uid": user.id,
            "workspace_id": str(workspace["workspace_id"]),
            "purpose": "jira_install",
            "iat": now,
            "exp": now + STATE_TTL,
        },
        _jwt_secret(),
        algorithm="HS256",
    )

    query = urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": jira_client.client_id(),
            "scope": " ".join(jira_client.SCOPES),
            "redirect_uri": _redirect_uri(),
            "state": state,
            "response_type": "code",
            # Without prompt=consent Atlassian skips the screen on a reconnect
            # and returns no refresh token, which breaks the install an hour in.
            "prompt": "consent",
        }
    )
    return InstallUrlOut(url=f"{jira_client.AUTH_BASE}/authorize?{query}")


@router.get("/callback")
async def install_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Where Atlassian sends the user back after they approve (or decline).

    Every failure path here is a *browser* redirect carrying a reason, not a
    JSON error: the user is mid-navigation and the Sources page is what has to
    explain what went wrong.
    """

    def fail(reason: str) -> RedirectResponse:
        return RedirectResponse(f"{_frontend_url()}/sources?jira=error&reason={reason}")

    if error or not code or not state:
        return fail(error or "cancelled")

    try:
        claims = jwt.decode(state, _jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return fail("bad_state")

    if claims.get("purpose") != "jira_install":
        return fail("bad_state")

    try:
        tokens = await jira_client.exchange_code(code, _redirect_uri())
        sites = await jira_client.accessible_resources(tokens.access_token)
    except (jira_client.JiraError, httpx.HTTPError) as exc:
        log.warning("jira oauth exchange failed: %s", exc)
        return fail("exchange")

    if not sites:
        # The grant covers no Jira site — usually a Confluence-only account.
        return fail("no_site")

    # The consent screen is single-site, so the first entry is the one the user
    # picked. A multi-site grant would need a picker; deliberately out of scope.
    site = sites[0]

    install = await asyncio.to_thread(
        jira_db.upsert_installation,
        cloud_id=site.cloud_id,
        site_name=site.name,
        site_url=site.url,
        workspace_id=claims["workspace_id"],
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_at=tokens.expires_at,
        scopes=tokens.scopes,
        webhook_secret=secrets.token_urlsafe(32),
        installed_by=claims["uid"],
    )

    # Subscribe now, while we know the token is fresh. A refusal here is not
    # fatal — the status endpoint surfaces the manual URL instead.
    webhook_id = await jira_client.register_webhook(
        site.cloud_id,
        tokens.access_token,
        _webhook_url(install["webhook_secret"]),
    )
    if webhook_id:
        await asyncio.to_thread(jira_db.update_webhook, str(install["id"]), webhook_id)
    else:
        log.info("jira dynamic webhook refused for %s; manual setup required", site.cloud_id)

    return RedirectResponse(f"{_frontend_url()}/sources?jira=connected")


@router.get("/status", response_model=JiraStatusOut)
async def status(
    tasks: BackgroundTasks, user: UserOut = Depends(current_user)
) -> JiraStatusOut:
    workspace_id = (await workspace_for(user))["workspace_id"]
    install = await asyncio.to_thread(
        jira_db.get_installation_by_workspace, workspace_id
    )
    stats = await asyncio.to_thread(jira_db.source_event_stats, workspace_id, "jira")

    if install is None:
        return JiraStatusOut(
            configured=jira_client.is_configured(),
            connected=False,
            received=stats["received"] or 0,
            stored=stats["stored"] or 0,
            quarantined=stats["quarantined"] or 0,
            dropped=stats["dropped"] or 0,
            last_event_at=stats["last_event_at"],
        )

    # Atlassian expires a dynamic webhook 30 days after registration. This poll
    # is the only thing guaranteed to run while a workspace is in use, so it is
    # where the extension happens — in the background, since a slow Atlassian
    # must not make the Sources page hang.
    if _webhook_is_stale(install):
        tasks.add_task(extend_webhook, dict(install))

    return JiraStatusOut(
        configured=jira_client.is_configured(),
        connected=True,
        site_name=install["site_name"],
        site_url=install["site_url"],
        installed_at=install["installed_at"],
        last_synced_at=install["last_synced_at"],
        webhook_active=install["webhook_id"] is not None,
        webhook_url=_webhook_url(install["webhook_secret"]),
        received=stats["received"] or 0,
        stored=stats["stored"] or 0,
        quarantined=stats["quarantined"] or 0,
        dropped=stats["dropped"] or 0,
        last_event_at=stats["last_event_at"],
    )


def _webhook_is_stale(install: dict) -> bool:
    if not install["webhook_id"]:
        return False
    registered = install["webhook_registered_at"]
    if registered is None:
        return True
    if registered.tzinfo is None:
        registered = registered.replace(tzinfo=UTC)
    age = datetime.now(UTC) - registered
    return age > timedelta(days=jira_client.WEBHOOK_REFRESH_AFTER_DAYS)


async def extend_webhook(install: dict) -> None:
    """Push the webhook expiry out another 30 days."""
    try:
        token = await _token(install)
        ok = await jira_client.refresh_webhook(
            install["cloud_id"], token, install["webhook_id"]
        )
        if ok:
            await asyncio.to_thread(
                jira_db.update_webhook, str(install["id"]), install["webhook_id"]
            )
        else:
            log.warning("jira webhook refresh failed for %s", install["cloud_id"])
    except Exception:  # noqa: BLE001 - background task; nothing catches above us
        log.exception("jira webhook refresh crashed for %s", install["cloud_id"])


@router.delete("/disconnect")
async def disconnect(user: UserOut = Depends(current_user)) -> dict[str, bool]:
    """Forget the tokens. Captured memories stay — they are the product."""
    workspace = await workspace_for(user)
    if workspace["role"] != "owner":
        raise HTTPException(403, "only the workspace owner can disconnect Jira")

    install = await asyncio.to_thread(
        jira_db.get_installation_by_workspace, workspace["workspace_id"]
    )
    if install and install["webhook_id"]:
        # Best effort: unsubscribe before dropping the row, so Jira stops
        # delivering to a URL that no longer resolves to anything.
        try:
            token = await _token(dict(install))
            await jira_client.delete_webhook(
                install["cloud_id"], token, install["webhook_id"]
            )
        except (jira_client.JiraError, httpx.HTTPError) as exc:
            log.warning("jira webhook delete failed: %s", exc)

    removed = await asyncio.to_thread(
        jira_db.delete_installation, workspace["workspace_id"]
    )
    return {"ok": removed}


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


@router.get("/activity", response_model=list[SourceEventOut])
async def activity(
    limit: int = 25, user: UserOut = Depends(current_user)
) -> list[SourceEventOut]:
    """The audit feed: what arrived from Jira, and what capture decided."""
    workspace_id = (await workspace_for(user))["workspace_id"]
    rows = await asyncio.to_thread(
        jira_db.recent_source_events, workspace_id, min(limit, 100), "jira"
    )
    return [
        SourceEventOut(
            id=str(r["id"]),
            author=r["author"],
            text=r["text"],
            outcome=r["outcome"],
            reason=r["reason"],
            occurred_at=r["occurred_at"],
            memory_id=str(r["memory_id"]) if r["memory_id"] else None,
            memory_title=r["memory_title"],
            memory_type=r["memory_type"],
        )
        for r in rows
    ]


# --- webhook ----------------------------------------------------------------

# Which deliveries are worth the pipeline's time. Jira fires `issue_updated`
# for every field touch — a status transition, an assignee change, a sprint
# move — and none of those change the *text*. Re-ingesting them would mean an
# LLM call per drag of a card across a board, all of them classifying prose we
# already saw.
_TEXT_FIELDS = {"description", "summary"}


def _changed_text(body: dict) -> bool:
    """True when an `issue_updated` actually touched prose we care about."""
    items = ((body.get("changelog") or {}).get("items")) or []
    return any((i.get("field") or "").lower() in _TEXT_FIELDS for i in items)


@router.post("/webhook/{secret}")
async def webhook(secret: str, body: dict, tasks: BackgroundTasks) -> dict:
    """Inbound Jira event.

    Records, acks, and processes afterwards — a classifier call takes far
    longer than Jira is willing to wait, and a slow non-2xx makes it retry.
    """
    install = await asyncio.to_thread(jira_db.get_installation_by_secret, secret)
    if install is None:
        # Constant-time comparison is moot here (the lookup already failed), but
        # the response must not distinguish "wrong secret" from "disconnected".
        raise HTTPException(404, "unknown webhook")

    event_name = body.get("webhookEvent") or ""
    issue = body.get("issue") or {}
    issue_key = issue.get("key") or ""
    if not issue_key:
        return {"ok": True}

    fields = issue.get("fields") or {}
    project_key = (fields.get("project") or {}).get("key") or ""
    comment = body.get("comment") or {}

    if event_name in ("comment_created", "comment_updated"):
        kind = "comment"
        revision = str(comment.get("id") or "")
        author = (comment.get("author") or {}).get("displayName")
        text = jira_client.adf_to_text(comment.get("body"))
        occurred_at = _parse_jira_time(comment.get("updated") or comment.get("created"))
    elif event_name in ("jira:issue_created", "jira:issue_updated"):
        if event_name == "jira:issue_updated" and not _changed_text(body):
            # The criterion that keeps a board full of status drags from
            # becoming a bill. Not recorded as a source_event at all: there is
            # no new content to audit.
            return {"ok": True}
        kind = "issue"
        # `updated` distinguishes successive edits of the same issue; without it
        # every revision collides on one external_id and only the first lands.
        revision = str(fields.get("updated") or fields.get("created") or "")
        author = (fields.get("reporter") or {}).get("displayName")
        text = jira_client.adf_to_text(fields.get("description"))
        occurred_at = _parse_jira_time(fields.get("updated") or fields.get("created"))
    else:
        return {"ok": True}

    summary = fields.get("summary") or ""
    external_id = f"jira:{issue_key}:{kind}:{revision or '0'}"

    row_id = await asyncio.to_thread(
        jira_db.record_source_event,
        workspace_id=install["workspace_id"],
        source="jira",
        external_id=external_id,
        author=author,
        text=f"{summary}\n\n{text}".strip(),
        occurred_at=occurred_at,
        payload=body,
    )
    if row_id is None:
        # Already recorded: this is one of Jira's retries.
        return {"ok": True}

    payload = JiraPayload(
        project_key=project_key,
        issue_key=issue_key,
        summary=summary,
        description=text if kind == "issue" else "",
        comment=text if kind == "comment" else "",
        comment_author=author if kind == "comment" else None,
        reporter=(fields.get("reporter") or {}).get("displayName"),
        created_at=occurred_at,
        issue_type=(fields.get("issuetype") or {}).get("name"),
        status=(fields.get("status") or {}).get("name"),
        url=jira_client.issue_url(install["site_url"], issue_key),
        kind=kind,
        revision=revision or None,
        webhook_event=event_name,
    )

    tasks.add_task(process_event, row_id, install["workspace_id"], payload)
    return {"ok": True}


def _parse_jira_time(value: str | None) -> datetime:
    """Jira stamps look like `2026-08-18T11:04:22.417+0500` — an offset with no
    colon, which `fromisoformat` rejects before 3.11 and still trips over when
    the milliseconds are absent."""
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.now(UTC)


async def process_event(row_id: str, workspace_id: str, payload: JiraPayload) -> None:
    """Run one recorded event through the capture pipeline, then close its row.

    Runs after the response has gone back to Jira. Every exit path writes an
    outcome — a row left at 'pending' means the worker died mid-flight, and
    that is exactly the signal you want it to be.
    """
    try:
        request = JiraEventIn(
            source="jira", workspace_id=workspace_id, payload=payload
        )
        result = await ingest(
            normalize(request),
            workspace_id=workspace_id,
            provider=get_provider(),
            store=get_store(),
        )
        await asyncio.to_thread(
            jira_db.finish_source_event,
            row_id,
            outcome=result.outcome,
            reason=result.reason,
            memory_id=result.memory.id if result.memory else None,
        )
    except (ClassificationError, ProviderError) as exc:
        # The event was fine; the model was not. Left as 'error' so it can be
        # replayed rather than silently counted as "nothing worth storing".
        log.warning("jira ingest failed for %s: %s", row_id, exc)
        await asyncio.to_thread(
            jira_db.finish_source_event, row_id, outcome="error", reason=str(exc)
        )
    except Exception as exc:  # noqa: BLE001 - background task; nothing catches above us
        log.exception("jira ingest crashed for %s", row_id)
        await asyncio.to_thread(
            jira_db.finish_source_event, row_id, outcome="error", reason=str(exc)
        )


# --- backfill ---------------------------------------------------------------


class SyncOut(BaseModel):
    queued: int
    skipped: int
    reason: str


@router.post("/sync", response_model=SyncOut)
async def sync(tasks: BackgroundTasks, user: UserOut = Depends(current_user)) -> SyncOut:
    """Pull recent issues through the pipeline.

    Webhooks only cover what happens after connecting, and on the day you
    connect every decision worth remembering is already in the backlog. This is
    what makes the first hour of the integration useful instead of empty.
    """
    workspace = await workspace_for(user)
    install = await asyncio.to_thread(
        jira_db.get_installation_by_workspace, workspace["workspace_id"]
    )
    if install is None:
        raise HTTPException(404, "Jira is not connected")

    try:
        token = await _token(dict(install))
    except (jira_client.JiraError, httpx.HTTPError) as exc:
        raise HTTPException(502, f"could not refresh the Jira token: {exc}") from exc

    # Only what changed since the last pass, or the recent past on a first run.
    # Ordered oldest-first so a superseded decision is ingested before the one
    # that replaces it.
    since = install["last_synced_at"] or (
        datetime.now(UTC) - timedelta(days=SYNC_LOOKBACK_DAYS)
    )
    jql = f'updated >= "{since.strftime("%Y-%m-%d %H:%M")}" ORDER BY updated ASC'

    try:
        issues = await jira_client.search_issues(
            install["cloud_id"], token, jql, SYNC_LIMIT
        )
    except (jira_client.JiraError, httpx.HTTPError) as exc:
        raise HTTPException(502, f"Jira search failed: {exc}") from exc

    queued = skipped = 0
    for issue in issues:
        fields = issue.get("fields") or {}
        issue_key = issue.get("key") or ""
        revision = str(fields.get("updated") or fields.get("created") or "")
        text = jira_client.adf_to_text(fields.get("description"))
        summary = fields.get("summary") or ""
        author = (fields.get("reporter") or {}).get("displayName")
        occurred_at = _parse_jira_time(fields.get("updated") or fields.get("created"))

        row_id = await asyncio.to_thread(
            jira_db.record_source_event,
            workspace_id=install["workspace_id"],
            source="jira",
            external_id=f"jira:{issue_key}:issue:{revision or '0'}",
            author=author,
            text=f"{summary}\n\n{text}".strip(),
            occurred_at=occurred_at,
            payload=issue,
        )
        if row_id is None:
            # Seen already — either a webhook beat the backfill to it, or this
            # revision was pulled by an earlier sync.
            skipped += 1
            continue

        payload = JiraPayload(
            project_key=(fields.get("project") or {}).get("key") or "",
            issue_key=issue_key,
            summary=summary,
            description=text,
            reporter=author,
            created_at=occurred_at,
            issue_type=(fields.get("issuetype") or {}).get("name"),
            status=(fields.get("status") or {}).get("name"),
            url=jira_client.issue_url(install["site_url"], issue_key),
            kind="issue",
            revision=revision or None,
            webhook_event="backfill",
        )
        tasks.add_task(process_event, row_id, install["workspace_id"], payload)
        queued += 1

    await asyncio.to_thread(jira_db.mark_synced, str(install["id"]))

    return SyncOut(
        queued=queued,
        skipped=skipped,
        reason=f"{len(issues)} issues updated since {since:%Y-%m-%d}",
    )
