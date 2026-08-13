"""Google sign-in.

The browser gets a signed ID token from Google, posts it here once, and we
exchange it for our own JWT carried in an HttpOnly cookie. Verification is the
whole security boundary: everything downstream trusts our JWT, so the ID token
check has to be strict.

Stateless by choice — there is no session table, so the JWT *is* the session.
The tradeoff is that a token cannot be revoked before it expires; sign-out
clears the cookie but a copy taken beforehand stays valid until `exp`. Keep
JWT_TTL_DAYS short enough that this is acceptable.

Endpoints are sync `def`, not `async def`: the token verification does blocking
HTTP (fetching Google's signing certs) and the connection pool is sync, so
FastAPI running these in its threadpool is what keeps the event loop free.
"""

import os
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel

from db import workspaces as workspaces_db
from db.session import get_conn

router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_ALG = "HS256"
COOKIE_NAME = "ems_token"

# Read at call time, not import time. `app.main` imports this router before it
# calls load_dotenv(), so anything resolved at module level sees the process
# environment as it was *before* .env was loaded — which is to say, empty.


def _google_client_id() -> str:
    return os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "")


def _jwt_ttl() -> timedelta:
    return timedelta(days=int(os.getenv("JWT_TTL_DAYS", "30")))


def _cookie_secure() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


class GoogleLoginRequest(BaseModel):
    credential: str  # the JWT the Google button hands to the browser


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    avatar_url: str | None = None


def _issue_token(user_id: str, email: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": user_id, "email": email, "iat": now, "exp": now + _jwt_ttl()},
        _jwt_secret(),
        algorithm=JWT_ALG,
    )


def current_user(ems_token: str | None = Cookie(default=None)) -> UserOut:
    """Dependency for any route that needs a signed-in user."""
    if not ems_token:
        raise HTTPException(401, "not authenticated")

    try:
        claims = jwt.decode(ems_token, _jwt_secret(), algorithms=[JWT_ALG])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid or expired token") from exc

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, name, avatar_url FROM users WHERE id = %s",
            (claims["sub"],),
        )
        row = cur.fetchone()

    # The token can outlive the row it points at.
    if row is None:
        raise HTTPException(401, "user no longer exists")

    return UserOut(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        avatar_url=row["avatar_url"],
    )


@router.post("/google", response_model=UserOut)
def google_login(body: GoogleLoginRequest, response: Response) -> UserOut:
    client_id = _google_client_id()
    if not client_id or not _jwt_secret():
        raise HTTPException(
            503,
            "auth is not configured: set GOOGLE_OAUTH_CLIENT_ID and JWT_SECRET "
            "in backend/.env",
        )

    try:
        # Checks the signature against Google's public keys, and that `aud`
        # matches our client ID, `iss` is Google, and the token has not expired.
        # Anything less and a token minted for a different app would pass.
        claims = id_token.verify_oauth2_token(
            body.credential, google_requests.Request(), client_id
        )
    except ValueError as exc:
        raise HTTPException(401, "invalid Google token") from exc

    # An unverified address is not proof of anything, and it is what the row is
    # keyed on for humans reading the table.
    if not claims.get("email_verified"):
        raise HTTPException(403, "Google account has no verified email")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (google_sub, email, name, avatar_url, last_login_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (google_sub) DO UPDATE
                SET email         = excluded.email,
                    name          = excluded.name,
                    avatar_url    = excluded.avatar_url,
                    last_login_at = now()
            RETURNING id, email, name, avatar_url;
            """,
            (
                claims["sub"],
                claims["email"].lower(),
                claims.get("name"),
                claims.get("picture"),
            ),
        )
        row = cur.fetchone()

    user = UserOut(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        avatar_url=row["avatar_url"],
    )

    # Join a pending invite (added by a workspace owner before this user ever
    # signed in) automatically -- that's accepting an existing invite, not
    # onboarding. A bare login otherwise creates nothing: a first-time user
    # has no workspace until they finish onboarding (POST /api/workspaces).
    workspaces_db.resolve_pending_invite(user.id, user.email)

    response.set_cookie(
        COOKIE_NAME,
        _issue_token(user.id, user.email),
        httponly=True,  # unreadable from JS, so XSS cannot lift the token
        secure=_cookie_secure(),
        samesite="lax",  # not sent on cross-site POSTs, which covers CSRF here
        max_age=int(_jwt_ttl().total_seconds()),
        path="/",
    )
    return user


@router.get("/me", response_model=UserOut)
def me(user: UserOut = Depends(current_user)) -> UserOut:
    return user


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
