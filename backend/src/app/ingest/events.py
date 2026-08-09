"""Source payloads → one normalized Event.

Scope §6: every connector normalizes to a common Event shape before the filter
and extraction stages, so those stages never learn what Slack is. Slack is the
source that actually matters right now (highest value, worst noise); GitHub and
Jira are here to keep the seam honest — if the Event shape only ever had one
producer it would silently grow Slack-specific fields.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Source = Literal["slack", "github", "jira"]


@dataclass(slots=True)
class Event:
    """What the pipeline consumes. Source-agnostic by construction."""

    source: Source
    external_id: str
    text: str
    author: str
    occurred_at: datetime
    scope: str
    context: str  # channel name, repo, or project key — for prompt context
    url: str | None = None
    is_bot: bool = False
    subtype: str | None = None
    metadata: dict = field(default_factory=dict)


# --- Slack ------------------------------------------------------------------


class SlackPayload(BaseModel):
    """A Slack Events API `message` event, trimmed to the fields we use."""

    channel: str
    text: str
    user: str | None = None
    ts: str  # Slack epoch-with-fraction, e.g. "1730000000.000100"
    channel_name: str | None = None
    user_name: str | None = None
    thread_ts: str | None = None
    subtype: str | None = None
    bot_id: str | None = None
    permalink: str | None = None


class SlackEventIn(BaseModel):
    source: Literal["slack"]
    workspace_id: str = Field(min_length=1)
    scope: str | None = None
    payload: SlackPayload


def _from_slack_ts(ts: str) -> datetime:
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def _normalize_slack(request: SlackEventIn) -> Event:
    p = request.payload
    channel = p.channel_name or p.channel
    return Event(
        source="slack",
        external_id=f"slack:{p.channel}:{p.ts}",
        text=p.text,
        author=p.user_name or p.user or "unknown",
        occurred_at=_from_slack_ts(p.ts),
        # Slack channels don't map cleanly onto repos or projects, so absent an
        # explicit scope a message is workspace-wide rather than guessed at.
        scope=request.scope or "workspace",
        context=f"#{channel}",
        url=p.permalink,
        is_bot=p.bot_id is not None,
        subtype=p.subtype,
        metadata={"channel": p.channel, "thread_ts": p.thread_ts},
    )


# --- GitHub -----------------------------------------------------------------


class GitHubPayload(BaseModel):
    repo: str
    title: str | None = None
    body: str = ""
    author: str | None = None
    created_at: datetime | None = None
    number: int | None = None
    kind: str = "pull_request"  # pull_request | issue | review_comment
    url: str | None = None


class GitHubEventIn(BaseModel):
    source: Literal["github"]
    workspace_id: str = Field(min_length=1)
    scope: str | None = None
    payload: GitHubPayload


def _normalize_github(request: GitHubEventIn) -> Event:
    p = request.payload
    # A PR's title carries the claim and the body carries the rationale; the
    # extractor needs both or it invents one from the other.
    text = f"{p.title}\n\n{p.body}".strip() if p.title else p.body
    return Event(
        source="github",
        external_id=f"github:{p.repo}:{p.kind}:{p.number or p.url or p.title}",
        text=text,
        author=p.author or "unknown",
        occurred_at=p.created_at or datetime.now(UTC),
        scope=request.scope or f"repo:{p.repo}",
        context=f"{p.repo} {p.kind}",
        url=p.url,
        metadata={"repo": p.repo, "number": p.number, "kind": p.kind},
    )


# --- Jira -------------------------------------------------------------------


class JiraPayload(BaseModel):
    project_key: str
    issue_key: str
    summary: str
    description: str = ""
    reporter: str | None = None
    created_at: datetime | None = None
    issue_type: str | None = None
    status: str | None = None
    url: str | None = None


class JiraEventIn(BaseModel):
    source: Literal["jira"]
    workspace_id: str = Field(min_length=1)
    scope: str | None = None
    payload: JiraPayload


def _normalize_jira(request: JiraEventIn) -> Event:
    p = request.payload
    text = f"{p.summary}\n\n{p.description}".strip()
    return Event(
        source="jira",
        external_id=f"jira:{p.issue_key}",
        text=text,
        author=p.reporter or "unknown",
        occurred_at=p.created_at or datetime.now(UTC),
        scope=request.scope or f"project:{p.project_key}",
        context=f"{p.issue_key} ({p.issue_type or 'issue'})",
        url=p.url,
        metadata={"issue_key": p.issue_key, "status": p.status},
    )


# `source` discriminates, so FastAPI validates the right payload shape and the
# error message names the offending field instead of dumping all three schemas.
EventIn = Annotated[
    SlackEventIn | GitHubEventIn | JiraEventIn,
    Field(discriminator="source"),
]

_NORMALIZERS = {
    "slack": _normalize_slack,
    "github": _normalize_github,
    "jira": _normalize_jira,
}


def normalize(request: SlackEventIn | GitHubEventIn | JiraEventIn) -> Event:
    return _NORMALIZERS[request.source](request)
