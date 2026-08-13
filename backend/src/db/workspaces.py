"""Queries for workspaces, membership, and pending email invites.

A user can belong to several workspaces at once. `users.active_workspace_id`
says which one is "current" for routes that don't take an explicit
workspace_id -- the Slack connector, /api/workspaces/me. This is what lets a
Slack integration installed by one workspace member be immediately visible to
a teammate added later: once they're a member, switching their active
workspace to it points every workspace-scoped table
(`slack_installations`, `memories`, `source_events`) at the same
`workspace_id`.

All functions here are blocking (the pool is sync). Callers on the event loop
must wrap them in `asyncio.to_thread`.
"""

from db.session import get_conn

# --- personal workspace bootstrap --------------------------------------------


def get_or_create_personal_workspace(user_id: str, name: str) -> dict:
    """Ensure `user_id` has a personal workspace, creating one if needed.

    Only sets it *active* if the user has no active workspace yet -- a
    returning user with an active team workspace shouldn't get bounced back
    to their personal one just because this runs on every login.

    The personal workspace's id is set to the user's own id -- see
    `db.init_db.BACKFILL_WORKSPACES_SQL` for why that convention matters.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO workspaces (id, name, owner_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
            """,
            (user_id, name, user_id),
        )
        cur.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role)
            VALUES (%s, %s, 'owner')
            ON CONFLICT (workspace_id, user_id) DO NOTHING;
            """,
            (user_id, user_id),
        )
        cur.execute(
            """
            UPDATE users SET active_workspace_id = %s
            WHERE id = %s AND active_workspace_id IS NULL;
            """,
            (user_id, user_id),
        )

    return get_workspace_for_user(user_id)


# --- invites ------------------------------------------------------------------


def resolve_pending_invite(user_id: str, email: str) -> dict | None:
    """If `email` has a pending invite, join that workspace and switch to it.

    Returns the joined workspace, or `None` if there was nothing to resolve.
    Landing straight in the shared workspace -- not just becoming a member of
    it -- is the point of the invite: no manual switch to see the connected
    Slack integration.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT workspace_id FROM workspace_invites
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT 1;
            """,
            (email,),
        )
        invite = cur.fetchone()
        if invite is None:
            return None

        workspace_id = invite["workspace_id"]
        cur.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role)
            VALUES (%s, %s, 'member')
            ON CONFLICT (workspace_id, user_id) DO NOTHING;
            """,
            (workspace_id, user_id),
        )
        cur.execute(
            "UPDATE users SET active_workspace_id = %s WHERE id = %s;",
            (workspace_id, user_id),
        )
        cur.execute("DELETE FROM workspace_invites WHERE email = %s;", (email,))

    return get_workspace_for_user(user_id)


def add_member_by_email(workspace_id: str, email: str, invited_by: str) -> dict:
    """Add a teammate to a workspace by email.

    If they already have an account, they become a member immediately (their
    existing memberships and active workspace are untouched -- they'll switch
    to this one themselves). Otherwise the invite sits pending until they
    complete Google login with that email.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
        user = cur.fetchone()

        if user is not None:
            cur.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role)
                VALUES (%s, %s, 'member')
                ON CONFLICT (workspace_id, user_id) DO NOTHING;
                """,
                (workspace_id, user["id"]),
            )
            return {"status": "joined", "user_id": str(user["id"])}

        cur.execute(
            """
            INSERT INTO workspace_invites (workspace_id, email, invited_by)
            VALUES (%s, %s, %s)
            ON CONFLICT (workspace_id, email) DO NOTHING;
            """,
            (workspace_id, email, invited_by),
        )
        return {"status": "invited", "user_id": None}


# --- membership lookups ---------------------------------------------------


def get_workspace_for_user(user_id: str) -> dict | None:
    """The user's *active* workspace -- id, name, and their role in it."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id AS workspace_id, w.name AS workspace_name, wm.role
            FROM users u
            JOIN workspace_members wm
                ON wm.user_id = u.id AND wm.workspace_id = u.active_workspace_id
            JOIN workspaces w ON w.id = wm.workspace_id
            WHERE u.id = %s;
            """,
            (user_id,),
        )
        row = cur.fetchone()

    # workspace_id travels from here into workspace_id columns on
    # slack_installations / memories / source_events, which are plain STRING
    # (not UUID) -- psycopg hands back a UUID object for the `workspaces.id`
    # column, and CockroachDB rejects comparing that against a STRING column.
    # Stringify once at the source rather than at every call site.
    if row is not None:
        row["workspace_id"] = str(row["workspace_id"])
    return row


def rename_workspace(workspace_id: str, name: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE workspaces SET name = %s WHERE id = %s;", (name, workspace_id))


def list_workspaces_for_user(user_id: str) -> list[dict]:
    """Every workspace the user belongs to, for the workspace switcher."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id AS workspace_id, w.name AS workspace_name, wm.role
            FROM workspace_members wm
            JOIN workspaces w ON w.id = wm.workspace_id
            WHERE wm.user_id = %s
            ORDER BY w.name;
            """,
            (user_id,),
        )
        return cur.fetchall()


def switch_active_workspace(user_id: str, workspace_id: str) -> dict | None:
    """Point the user's active workspace at `workspace_id`.

    Returns the newly active workspace, or `None` if the user isn't a member
    of it -- the API layer turns that into a 403 rather than letting someone
    switch into a workspace they don't belong to.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM workspace_members WHERE workspace_id = %s AND user_id = %s;",
            (workspace_id, user_id),
        )
        if cur.fetchone() is None:
            return None

        cur.execute(
            "UPDATE users SET active_workspace_id = %s WHERE id = %s;",
            (workspace_id, user_id),
        )

    return get_workspace_for_user(user_id)


def list_members(workspace_id: str) -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.id AS user_id, u.email, u.name, wm.role
            FROM workspace_members wm
            JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id = %s
            ORDER BY wm.role, u.email;
            """,
            (workspace_id,),
        )
        return cur.fetchall()


def remove_member(workspace_id: str, user_id: str) -> None:
    """Remove a member. If that was their active workspace, switch them to
    another one they still belong to, bootstrapping a personal workspace only
    if none remain."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM workspace_members WHERE workspace_id = %s AND user_id = %s;",
            (workspace_id, user_id),
        )
        cur.execute(
            "SELECT active_workspace_id FROM users WHERE id = %s;", (user_id,)
        )
        user = cur.fetchone()

    if str(user["active_workspace_id"]) != str(workspace_id):
        return

    remaining = list_workspaces_for_user(user_id)
    if remaining:
        switch_active_workspace(user_id, remaining[0]["workspace_id"])
        return

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT name, email FROM users WHERE id = %s;", (user_id,))
        row = cur.fetchone()
    get_or_create_personal_workspace(user_id, row["name"] or row["email"])
    # active_workspace_id still points at the just-removed membership (not
    # NULL), so the NULL-guarded switch inside get_or_create_personal_workspace
    # won't have applied -- force it explicitly.
    switch_active_workspace(user_id, user_id)
