"""Workspace membership.

A workspace owner adds teammates by email so they land in the same workspace
as an already-connected Slack integration — no second OAuth flow. A user can
belong to several workspaces; see `db.workspaces` for how "active workspace"
(what the Slack connector and `/me` operate on) is resolved.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import UserOut, current_user
from db import workspaces as workspaces_db

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class MemberOut(BaseModel):
    user_id: str
    email: str
    name: str | None = None
    role: str


class WorkspaceOut(BaseModel):
    id: str
    name: str
    role: str
    members: list[MemberOut]


class InviteRequest(BaseModel):
    email: str


class RenameRequest(BaseModel):
    name: str


class CreateRequest(BaseModel):
    name: str


class WorkspaceSummary(BaseModel):
    id: str
    name: str
    role: str
    active: bool


class SwitchRequest(BaseModel):
    workspace_id: str


@router.get("", response_model=list[WorkspaceSummary])
async def list_workspaces(user: UserOut = Depends(current_user)) -> list[WorkspaceSummary]:
    """Every workspace the user belongs to, for the workspace switcher."""
    active = await asyncio.to_thread(workspaces_db.get_workspace_for_user, user.id)
    active_id = active["workspace_id"] if active else None

    rows = await asyncio.to_thread(workspaces_db.list_workspaces_for_user, user.id)
    return [
        WorkspaceSummary(
            id=str(r["workspace_id"]),
            name=r["workspace_name"],
            role=r["role"],
            active=str(r["workspace_id"]) == active_id,
        )
        for r in rows
    ]


async def _require_workspace(user_id: str) -> dict:
    """The caller's active workspace, or a 404 if onboarding hasn't happened
    yet -- a first-time user has no workspace until POST /api/workspaces."""
    workspace = await asyncio.to_thread(workspaces_db.get_workspace_for_user, user_id)
    if workspace is None:
        raise HTTPException(404, "no workspace yet -- finish onboarding first")
    return workspace


async def _workspace_out(workspace: dict) -> WorkspaceOut:
    members = await asyncio.to_thread(workspaces_db.list_members, workspace["workspace_id"])
    return WorkspaceOut(
        id=str(workspace["workspace_id"]),
        name=workspace["workspace_name"],
        role=workspace["role"],
        members=[
            MemberOut(
                user_id=str(m["user_id"]), email=m["email"], name=m["name"], role=m["role"]
            )
            for m in members
        ],
    )


@router.post("/switch", response_model=WorkspaceOut)
async def switch_workspace(
    body: SwitchRequest, user: UserOut = Depends(current_user)
) -> WorkspaceOut:
    workspace = await asyncio.to_thread(
        workspaces_db.switch_active_workspace, user.id, body.workspace_id
    )
    if workspace is None:
        raise HTTPException(403, "not a member of that workspace")
    return await _workspace_out(workspace)


@router.post("", response_model=WorkspaceOut)
async def create_workspace(
    body: CreateRequest, user: UserOut = Depends(current_user)
) -> WorkspaceOut:
    """The onboarding flow's "name your workspace" step. This is the *only*
    place a workspace gets created -- logging in never creates one on its own
    (see `app.api.auth.google_login`), so a returning user always lands back
    on their existing workspace instead of a fresh one."""
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "name is required")

    workspace = await asyncio.to_thread(
        workspaces_db.get_or_create_personal_workspace, user.id, name
    )
    return await _workspace_out(workspace)


@router.get("/me", response_model=WorkspaceOut)
async def my_workspace(user: UserOut = Depends(current_user)) -> WorkspaceOut:
    workspace = await _require_workspace(user.id)
    return await _workspace_out(workspace)


@router.patch("/me", response_model=WorkspaceOut)
async def rename_workspace(
    body: RenameRequest, user: UserOut = Depends(current_user)
) -> WorkspaceOut:
    workspace = await _require_workspace(user.id)
    if workspace["role"] != "owner":
        raise HTTPException(403, "only the workspace owner can rename it")

    name = body.name.strip()
    if not name:
        raise HTTPException(422, "name is required")

    await asyncio.to_thread(workspaces_db.rename_workspace, workspace["workspace_id"], name)
    workspace["workspace_name"] = name
    return await _workspace_out(workspace)


@router.post("/invite")
async def invite(
    body: InviteRequest, user: UserOut = Depends(current_user)
) -> dict[str, str | None]:
    workspace = await _require_workspace(user.id)
    if workspace["role"] != "owner":
        raise HTTPException(403, "only the workspace owner can invite teammates")

    email = body.email.strip().lower()
    if not email:
        raise HTTPException(422, "email is required")

    result = await asyncio.to_thread(
        workspaces_db.add_member_by_email, workspace["workspace_id"], email, user.id
    )
    return result


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: str, user: UserOut = Depends(current_user)
) -> dict[str, bool]:
    workspace = await _require_workspace(user.id)
    if workspace["role"] != "owner":
        raise HTTPException(403, "only the workspace owner can remove teammates")
    if user_id == user.id:
        raise HTTPException(400, "the owner cannot remove themselves")

    await asyncio.to_thread(workspaces_db.remove_member, workspace["workspace_id"], user_id)
    return {"ok": True}
