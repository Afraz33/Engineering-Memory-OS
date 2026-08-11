"""Thin Slack Web API client.

Only the handful of methods the connector needs. Deliberately not the official
`slack_sdk`: that pulls in its own HTTP stack and an app framework we would use
none of, when this is four POSTs to a JSON endpoint.

Slack replies 200 with `{"ok": false, "error": "..."}` for application errors,
so a status check alone is not enough — `_call` inspects `ok`.
"""

import os
from dataclasses import dataclass

import httpx

SLACK_API = "https://slack.com/api"

# Read-only lookups whose answers effectively never change within a process
# lifetime. Without this, a busy channel means one users.info call per message.
_user_cache: dict[tuple[str, str], str] = {}
_channel_cache: dict[tuple[str, str], str] = {}

TIMEOUT = httpx.Timeout(10.0)


class SlackError(RuntimeError):
    """Slack rejected the call."""


@dataclass(slots=True)
class Installation:
    """What `oauth.v2.access` hands back once a user approves the install."""

    team_id: str
    team_name: str | None
    bot_token: str
    bot_user_id: str | None
    installer_user_id: str | None


def client_id() -> str:
    return os.getenv("SLACK_CLIENT_ID", "")


def client_secret() -> str:
    return os.getenv("SLACK_CLIENT_SECRET", "")


def signing_secret() -> str:
    return os.getenv("SLACK_SIGNING_SECRET", "")


def is_configured() -> bool:
    return bool(client_id() and client_secret() and signing_secret())


async def _call(method: str, token: str, **params) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        resp = await http.post(
            f"{SLACK_API}/{method}",
            headers={"Authorization": f"Bearer {token}"},
            data=params,
        )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("ok"):
        raise SlackError(f"{method}: {body.get('error', 'unknown error')}")
    return body


async def exchange_code(code: str, redirect_uri: str) -> Installation:
    """Turn the one-time `code` from the OAuth redirect into a bot token."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        resp = await http.post(
            f"{SLACK_API}/oauth.v2.access",
            data={
                "client_id": client_id(),
                "client_secret": client_secret(),
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("ok"):
        raise SlackError(f"oauth.v2.access: {body.get('error', 'unknown error')}")

    team = body.get("team") or {}
    return Installation(
        team_id=team.get("id", ""),
        team_name=team.get("name"),
        bot_token=body.get("access_token", ""),
        bot_user_id=body.get("bot_user_id"),
        installer_user_id=(body.get("authed_user") or {}).get("id"),
    )


async def user_name(token: str, team_id: str, user_id: str) -> str | None:
    """Slack events carry `U01ABC`, not a name. The classifier prompt and the
    provenance record both want something a human recognises."""
    if not user_id:
        return None
    key = (team_id, user_id)
    if key in _user_cache:
        return _user_cache[key]
    try:
        body = await _call("users.info", token, user=user_id)
    except (SlackError, httpx.HTTPError):
        return None
    profile = (body.get("user") or {}).get("profile") or {}
    name = (
        profile.get("display_name")
        or profile.get("real_name")
        or (body.get("user") or {}).get("name")
    )
    if name:
        _user_cache[key] = name
    return name


async def channel_name(token: str, team_id: str, channel_id: str) -> str | None:
    if not channel_id:
        return None
    key = (team_id, channel_id)
    if key in _channel_cache:
        return _channel_cache[key]
    try:
        body = await _call("conversations.info", token, channel=channel_id)
    except (SlackError, httpx.HTTPError):
        return None
    name = (body.get("channel") or {}).get("name")
    if name:
        _channel_cache[key] = name
    return name


async def permalink(token: str, channel_id: str, ts: str) -> str | None:
    """The provenance URL. Without it a memory cannot be traced back to the
    thread it came from, which Scope §6 treats as non-negotiable."""
    try:
        body = await _call(
            "chat.getPermalink", token, channel=channel_id, message_ts=ts
        )
    except (SlackError, httpx.HTTPError):
        return None
    return body.get("permalink")


async def post_message(
    token: str, channel: str, text: str, thread_ts: str | None = None
) -> None:
    """Used to answer slash-style commands in-thread."""
    params = {"channel": channel, "text": text}
    if thread_ts:
        params["thread_ts"] = thread_ts
    await _call("chat.postMessage", token, **params)
