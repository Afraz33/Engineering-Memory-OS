"""Thin Jira Cloud REST API client.

Only the handful of methods the connector needs. The client is responsible
only for Jira authentication and API communication.

Higher-level ingestion, normalization, chunking, and embeddings should stay
outside this class.

OAuth flow:
    1. User authorizes the app with Atlassian.
    2. Atlassian redirects back with a one-time code.
    3. exchange_code() exchanges the code for tokens.
    4. get_accessible_resources() tells us which Jira Cloud site(s) the
       installation can access.
"""

import os
from dataclasses import dataclass

import httpx


ATLASSIAN_API = ""
ATLASSIAN_AUTH = ""

TIMEOUT = httpx.Timeout(10.0)


class JiraError(RuntimeError):
    """Jira/Atlassian rejected the call."""


@dataclass(slots=True)
class Installation:
    """What Atlassian OAuth gives us after a user approves the installation."""

    cloud_id: str
    site_url: str | None
    site_name: str | None
    access_token: str
    refresh_token: str | None


def client_id() -> str:
    return os.getenv("JIRA_CLIENT_ID", "")


def client_secret() -> str:
    return os.getenv("JIRA_CLIENT_SECRET", "")


def is_configured() -> bool:
    return bool(client_id() and client_secret())


async def _call(
    method: str,
    token: str,
    cloud_id: str,
    path: str,
    **params,
) -> dict:
    """Make an authenticated Jira Cloud API request."""

    url = f"{ATLASSIAN_API}/ex/jira/{cloud_id}{path}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        response = await http.request(
            method,
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            params=params,
        )

    response.raise_for_status()

    body = response.json()

    if not isinstance(body, dict):
        raise JiraError(f"{path}: unexpected response")

    return body


async def exchange_code(
    code: str,
    redirect_uri: str,
) -> Installation:
    """Exchange the one-time OAuth authorization code for Jira tokens."""

    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        response = await http.post(
            f"{ATLASSIAN_AUTH}/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": client_id(),
                "client_secret": client_secret(),
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )

    response.raise_for_status()

    body = response.json()

    if "error" in body:
        raise JiraError(
            f"oauth/token: "
            f"{body.get('error_description', body.get('error', 'unknown error'))}"
        )

    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")

    if not access_token:
        raise JiraError("oauth/token: missing access_token")

    resources = await get_accessible_resources(access_token)

    if not resources:
        raise JiraError("No accessible Jira Cloud sites")

    site = resources[0]

    return Installation(
        cloud_id=site.get("id", ""),
        site_url=site.get("url"),
        site_name=site.get("name"),
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def get_accessible_resources(token: str) -> list[dict]:
    """Return Jira/Atlassian sites accessible by this OAuth token."""

    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        response = await http.get(
            f"{ATLASSIAN_AUTH}/oauth/token/accessible-resources",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )

    response.raise_for_status()

    body = response.json()

    if not isinstance(body, list):
        raise JiraError("accessible-resources: unexpected response")

    return body


async def get_issue(
    token: str,
    cloud_id: str,
    issue_key: str,
) -> dict:
    """Fetch one Jira issue."""

    return await _call(
        "GET",
        token,
        cloud_id,
        f"/rest/api/3/issue/{issue_key}",
        fields=(
            "summary,"
            "description,"
            "project,"
            "issuetype,"
            "status,"
            "priority,"
            "labels,"
            "components,"
            "reporter,"
            "assignee,"
            "created,"
            "updated"
        ),
    )


async def list_issues(
    token: str,
    cloud_id: str,
    jql: str,
    start_at: int = 0,
    max_results: int = 100,
) -> dict:
    """Search Jira issues using JQL.

    Example:
        project = ENG ORDER BY updated DESC
    """

    return await _call(
        "GET",
        token,
        cloud_id,
        "/rest/api/3/search",
        jql=jql,
        startAt=start_at,
        maxResults=max_results,
        fields=(
            "summary,"
            "description,"
            "project,"
            "issuetype,"
            "status,"
            "priority,"
            "labels,"
            "components,"
            "reporter,"
            "assignee,"
            "created,"
            "updated"
        ),
    )


async def get_comments(
    token: str,
    cloud_id: str,
    issue_key: str,
    start_at: int = 0,
    max_results: int = 100,
) -> dict:
    """Fetch comments for an issue.

    Keep this separate so comments can be added to the knowledge pipeline
    later without changing the basic Jira issue ingestion.
    """

    return await _call(
        "GET",
        token,
        cloud_id,
        f"/rest/api/3/issue/{issue_key}/comment",
        startAt=start_at,
        maxResults=max_results,
    )


async def get_projects(
    token: str,
    cloud_id: str,
) -> list[dict]:
    """Fetch projects available to the authenticated Jira user."""

    body = await _call(
        "GET",
        token,
        cloud_id,
        "/rest/api/3/project",
    )

    # Jira returns a list for this endpoint, while _call normally expects
    # a JSON object. If your API version returns a list directly, use a
    # dedicated request here instead.
    return body


def issue_url(
    site_url: str,
    issue_key: str,
) -> str:
    """Build the human-readable Jira issue URL."""

    return f"{site_url.rstrip('/')}/browse/{issue_key}"