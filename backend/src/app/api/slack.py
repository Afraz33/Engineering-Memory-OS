"""The Slack connector.

Four surfaces, and they have different trust models — which is why this is its
own router rather than more routes on `/api/events`:

    GET  /api/slack/install      browser, cookie-authenticated  → authorize URL
    GET  /api/slack/callback     browser, `state`-authenticated → stores token
    POST /api/slack/events       Slack,   signature-authenticated
    POST /api/slack/commands     Slack,   signature-authenticated

`/api/events` stays as it is: a hand-shaped envelope for tests and for other
connectors. Slack cannot use it, because Slack sends its own envelope, signs
the raw bytes, and hangs up after three seconds.

The three-second deadline is the constraint that shapes this file. A classifier
call takes far longer, so the webhook records the event, acks, and processes
afterwards. Slack retries anything it thinks failed, so the record step is also
what makes retries idempotent — see `db.slack.record_source_event`.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode

import httpx
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.auth import UserOut, current_user
from ai.ingest import ClassificationError, ingest, normalize
from ai.ingest.events.events import SlackEventIn, SlackPayload
from ai.memory import get_store
from ai.providers.llm import ChatMessage, ProviderError, get_provider
from ai.ingest.events.handlers.handle_ask import SYSTEM_PROMPT as ASK_SYSTEM_PROMPT
from db import slack as slack_db
from db import workspaces as workspaces_db
from services import slack_client

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slack", tags=["slack"])

# Bot scopes. `*:history` is what actually lets us read messages; `*:read`
# resolves channel ids to names; `users:read` resolves author ids to names;
# `chat:write` is only for answering commands. Adding a scope later forces
# every workspace to reinstall, so this list is deliberately complete.
SCOPES = (
    "channels:history",
    "channels:read",
    "groups:history",
    "groups:read",
    "users:read",
    "chat:write",
    "commands",
)

# Slack signs `v0:{timestamp}:{body}`. Anything older than this is a replay of
# a request we have already handled.
REPLAY_WINDOW_SECONDS = 60 * 5

STATE_TTL = timedelta(minutes=10)


# --- config -----------------------------------------------------------------
# Read at call time, not import time: `app.main` imports this router before it
# calls load_dotenv(), so module-level reads would see an empty environment.


def _frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def _redirect_uri() -> str:
    """Must byte-for-byte match the value registered in the Slack app config,
    and must be sent again on the token exchange or Slack rejects it."""
    return f"{_backend_url()}/api/slack/callback"


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "")


async def workspace_for(user: UserOut) -> dict:
    """Resolve the caller's *active* workspace (id, name, role).

    A user can belong to several workspaces (see `db.workspaces`); this is
    whichever one they last switched to.
    """
    return await asyncio.to_thread(workspaces_db.get_workspace_for_user, user.id)


# --- install flow -----------------------------------------------------------


class InstallUrlOut(BaseModel):
    url: str


class SlackStatusOut(BaseModel):
    configured: bool  # server has Slack credentials at all
    connected: bool
    team_name: str | None = None
    team_id: str | None = None
    installed_at: datetime | None = None
    received: int = 0
    stored: int = 0
    quarantined: int = 0
    dropped: int = 0
    last_event_at: datetime | None = None


@router.get("/install", response_model=InstallUrlOut)
async def install_url(user: UserOut = Depends(current_user)) -> InstallUrlOut:
    """Where to send the browser to start the install."""
    if not slack_client.is_configured():
        raise HTTPException(
            503,
            "Slack is not configured: set SLACK_CLIENT_ID, SLACK_CLIENT_SECRET "
            "and SLACK_SIGNING_SECRET in backend/.env",
        )

    workspace = await workspace_for(user)
    if workspace["role"] != "owner":
        raise HTTPException(403, "only the workspace owner can connect Slack")

    # `state` is a short-lived signed token, not a random nonce in a session
    # table: it survives the round trip through Slack, proves the callback
    # belongs to this user, and needs no server-side storage to verify. The
    # workspace id rides along too, so `/callback` needs no second DB lookup.
    now = datetime.now(UTC)
    state = jwt.encode(
        {
            "uid": user.id,
            "workspace_id": str(workspace["workspace_id"]),
            "purpose": "slack_install",
            "iat": now,
            "exp": now + STATE_TTL,
        },
        _jwt_secret(),
        algorithm="HS256",
    )

    query = urlencode(
        {
            "client_id": slack_client.client_id(),
            "scope": ",".join(SCOPES),
            "redirect_uri": _redirect_uri(),
            "state": state,
        }
    )
    return InstallUrlOut(url=f"https://slack.com/oauth/v2/authorize?{query}")


@router.get("/callback")
async def install_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Where Slack sends the user back after they approve (or decline)."""
    if error or not code or not state:
        return RedirectResponse(
            f"{_frontend_url()}/sources?slack=error&reason={error or 'cancelled'}"
        )

    try:
        claims = jwt.decode(state, _jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return RedirectResponse(f"{_frontend_url()}/sources?slack=error&reason=bad_state")

    if claims.get("purpose") != "slack_install":
        return RedirectResponse(f"{_frontend_url()}/sources?slack=error&reason=bad_state")

    try:
        install = await slack_client.exchange_code(code, _redirect_uri())
    except (slack_client.SlackError, httpx.HTTPError) as exc:
        log.warning("slack oauth exchange failed: %s", exc)
        return RedirectResponse(f"{_frontend_url()}/sources?slack=error&reason=exchange")

    await asyncio.to_thread(
        slack_db.upsert_installation,
        team_id=install.team_id,
        team_name=install.team_name,
        workspace_id=claims["workspace_id"],
        bot_token=install.bot_token,
        bot_user_id=install.bot_user_id,
        installed_by=claims["uid"],
    )

    return RedirectResponse(f"{_frontend_url()}/sources?slack=connected")


@router.get("/status", response_model=SlackStatusOut)
async def status(user: UserOut = Depends(current_user)) -> SlackStatusOut:
    workspace_id = (await workspace_for(user))["workspace_id"]
    install = await asyncio.to_thread(
        slack_db.get_installation_by_workspace, workspace_id
    )
    stats = await asyncio.to_thread(slack_db.source_event_stats, workspace_id, "slack")

    return SlackStatusOut(
        configured=slack_client.is_configured(),
        connected=install is not None,
        team_name=install["team_name"] if install else None,
        team_id=install["team_id"] if install else None,
        installed_at=install["installed_at"] if install else None,
        received=stats["received"] or 0,
        stored=stats["stored"] or 0,
        quarantined=stats["quarantined"] or 0,
        dropped=stats["dropped"] or 0,
        last_event_at=stats["last_event_at"],
    )


@router.delete("/disconnect")
async def disconnect(user: UserOut = Depends(current_user)) -> dict[str, bool]:
    """Forget the token. Captured memories stay — they are the product."""
    workspace = await workspace_for(user)
    if workspace["role"] != "owner":
        raise HTTPException(403, "only the workspace owner can disconnect Slack")

    removed = await asyncio.to_thread(
        slack_db.delete_installation, workspace["workspace_id"]
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
    """The audit feed: what arrived, and what the pipeline decided about it.

    This is the view that makes a silent drop debuggable — Scope §6.4.
    """
    workspace_id = (await workspace_for(user))["workspace_id"]
    rows = await asyncio.to_thread(
        slack_db.recent_source_events, workspace_id, min(limit, 100), "slack"
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


# --- request signing --------------------------------------------------------


async def verified_body(request: Request) -> bytes:
    """Authenticate an inbound Slack request, and hand back the raw bytes.

    The signature covers the *exact* bytes Slack sent, so this has to run on
    the raw body — re-serializing a parsed dict changes key order and spacing
    and the HMAC no longer matches.
    """
    secret = slack_client.signing_secret()
    if not secret:
        raise HTTPException(503, "SLACK_SIGNING_SECRET is not set")

    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")
    if not timestamp or not signature:
        raise HTTPException(401, "missing Slack signature headers")

    try:
        age = abs(time.time() - int(timestamp))
    except ValueError as exc:
        raise HTTPException(401, "malformed timestamp") from exc
    if age > REPLAY_WINDOW_SECONDS:
        raise HTTPException(401, "stale request")

    raw = await request.body()
    basestring = b"v0:" + timestamp.encode() + b":" + raw
    expected = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()

    # compare_digest, not ==: a short-circuiting comparison leaks how much of
    # the signature was correct.
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "bad signature")

    return raw


# --- events webhook ---------------------------------------------------------

# Edits and deletions arrive as a `message` event wrapping the original in
# `message`/`previous_message`. Treating them as new content would re-ingest
# text we already have under a different ts.
_SKIP_SUBTYPES = {"message_changed", "message_deleted", "thread_broadcast_changed"}


@router.post("/events")
async def events(
    request: Request,
    tasks: BackgroundTasks,
    raw: bytes = Depends(verified_body),
) -> dict:
    body = json.loads(raw)

    # Slack posts this once when you save the Request URL in the app config.
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge", "")}

    if body.get("type") != "event_callback":
        return {"ok": True}

    event = body.get("event") or {}
    team_id = body.get("team_id") or ""

    if event.get("type") != "message" or event.get("subtype") in _SKIP_SUBTYPES:
        return {"ok": True}

    install = await asyncio.to_thread(slack_db.get_installation_by_team, team_id)
    if install is None:
        # Uninstalled between the event firing and us handling it, or a stray
        # delivery. 200 regardless: a non-2xx makes Slack retry it three times.
        log.warning("slack event for unknown team %s", team_id)
        return {"ok": True}

    # Never ingest our own replies — `/ask` answers would otherwise loop back in
    # as candidate memories.
    if event.get("bot_id") or (
        install["bot_user_id"] and event.get("user") == install["bot_user_id"]
    ):
        return {"ok": True}

    channel, ts = event.get("channel", ""), event.get("ts", "")
    if not channel or not ts:
        return {"ok": True}

    # Same id `_normalize_slack` computes, so the audit row and the Event agree.
    external_id = f"slack:{channel}:{ts}"

    row_id = await asyncio.to_thread(
        slack_db.record_source_event,
        workspace_id=install["workspace_id"],
        source="slack",
        external_id=external_id,
        author=event.get("user"),
        text=event.get("text"),
        occurred_at=_from_slack_ts(ts),
        payload=body,
    )
    if row_id is None:
        # Already recorded: this is one of Slack's retries.
        return {"ok": True}

    tasks.add_task(process_event, row_id, dict(install), event)
    return {"ok": True}


def _from_slack_ts(ts: str) -> datetime:
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


async def process_event(row_id: str, install: dict, event: dict) -> None:
    """Run one recorded event through the capture pipeline, then close its row.

    Runs after the response has gone back to Slack. Every exit path writes an
    outcome — a row left at 'pending' means the worker died mid-flight, and
    that is exactly the signal you want it to be.
    """
    token = install["bot_token"]
    team_id = install["team_id"]
    channel = event.get("channel", "")
    ts = event.get("ts", "")

    try:
        # Slack sends ids, not names. The classifier prompt and the provenance
        # record both read much better with names, and the permalink is what
        # makes a memory traceable back to the thread.
        author, channel_label, link = await asyncio.gather(
            slack_client.user_name(token, team_id, event.get("user", "")),
            slack_client.channel_name(token, team_id, channel),
            slack_client.permalink(token, channel, ts),
        )

        request = SlackEventIn(
            source="slack",
            workspace_id=install["workspace_id"],
            payload=SlackPayload(
                channel=channel,
                text=event.get("text") or "",
                user=event.get("user"),
                ts=ts,
                channel_name=channel_label,
                user_name=author,
                thread_ts=event.get("thread_ts"),
                subtype=event.get("subtype"),
                bot_id=event.get("bot_id"),
                permalink=link,
            ),
        )

        result = await ingest(
            normalize(request),
            workspace_id=install["workspace_id"],
            provider=get_provider(),
            store=get_store(),
        )

        await asyncio.to_thread(
            slack_db.finish_source_event,
            row_id,
            outcome=result.outcome,
            reason=result.reason,
            memory_id=result.memory.id if result.memory else None,
        )

    except (ClassificationError, ProviderError) as exc:
        # The event was fine; the model was not. Left as 'error' so it can be
        # replayed rather than silently counted as "nothing worth storing".
        log.warning("slack ingest failed for %s: %s", row_id, exc)
        await asyncio.to_thread(
            slack_db.finish_source_event, row_id, outcome="error", reason=str(exc)
        )
    except Exception as exc:  # noqa: BLE001 - background task; nothing catches above us
        log.exception("slack ingest crashed for %s", row_id)
        await asyncio.to_thread(
            slack_db.finish_source_event, row_id, outcome="error", reason=str(exc)
        )


# --- slash commands ---------------------------------------------------------

# Slash commands are form-encoded and arrive on their own endpoint, not through
# the Events API. Same 3s deadline, but Slack also hands us a `response_url`
# good for 30 minutes — so the ack is immediate and the real answer follows.


@router.post("/commands")
async def commands(
    tasks: BackgroundTasks,
    raw: bytes = Depends(verified_body),
) -> dict:
    # `Form(...)` params would make FastAPI call `request.form()`, which reads
    # the body a second time — but `verified_body` already consumed the stream
    # to compute the signature, and Starlette doesn't cache it for re-reading.
    # Parsing the same `raw` bytes we already have avoids the double read.
    fields = parse_qs(raw.decode())
    command = fields.get("command", [""])[0]
    text = fields.get("text", [""])[0]
    team_id = fields.get("team_id", [""])[0]
    response_url = fields.get("response_url", [""])[0]

    install = await asyncio.to_thread(slack_db.get_installation_by_team, team_id)
    if install is None:
        return {"response_type": "ephemeral", "text": "This workspace is not connected."}

    if command != "/ask":
        return {"response_type": "ephemeral", "text": f"Unknown command {command}."}

    if not text.strip():
        return {"response_type": "ephemeral", "text": "Usage: `/ask <question>`"}

    tasks.add_task(answer_ask, dict(install), text, response_url)

    # `ephemeral` so the "thinking" line is visible only to the asker; the real
    # answer below posts `in_channel`.
    return {"response_type": "ephemeral", "text": f"Searching memory for “{text}”…"}


# How many memories to put in front of the model. Enough for context, few
# enough that the prompt stays cheap on a command anyone can spam.
ASK_CONTEXT_LIMIT = 12


async def answer_ask(install: dict, question: str, response_url: str) -> None:
    """Answer `/ask` from stored memories and post it back to the channel."""
    try:
        memories = await get_store().list(
            workspace_id=install["workspace_id"], statuses=["active"]
        )
        context = "\n\n".join(
            f"[{m.type}] {m.title}\n{m.body}" for m in memories[:ASK_CONTEXT_LIMIT]
        ) or "(no memories captured yet)"

        response = await get_provider().chat(
            [
                ChatMessage(
                    role="user",
                    content=f"Memory store:\n{context}\n\n---\nQuestion: {question}",
                )
            ],
            system=ASK_SYSTEM_PROMPT,
        )
        answer = response.content
    except Exception as exc:  # noqa: BLE001 - background task; nothing catches above us
        log.warning("slack /ask failed: %s", exc)
        answer = "Could not reach the memory store just now."

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as http:
        await http.post(
            response_url,
            json={"response_type": "in_channel", "text": answer},
        )
