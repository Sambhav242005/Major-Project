"""Project memory sharing router — grant/revoke/list cross-project memory access."""

import uuid

from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.security import get_current_user, User
from core.deps import _user_uuid
from db.models import ProjectMember
from db.session import get_db
from services import sharing as sharing_service

router = APIRouter()


async def require_project_member(db, project_id, user, *, write=False):
    try:
        identifier = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    member = (await db.execute(select(ProjectMember).where(
        ProjectMember.project_id == identifier,
        ProjectMember.user_id == _user_uuid(user.id),
    ))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Project not found")
    if write and member.role not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="Only editors can change memory sharing")


class ShareGrantRequest(BaseModel):
    target_project_id: str
    permission: str = "read"  # read | read_write


@router.get("")
async def list_my_shares(
    project_id: str = Path(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all shares this project has given to others."""
    await require_project_member(db, project_id, user)
    shares = await sharing_service.list_shares_given_to(db, project_id)
    return {"shares": shares}


@router.get("/received")
async def list_received_shares(
    project_id: str = Path(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all shares other projects have given to this project."""
    await require_project_member(db, project_id, user)
    shares = await sharing_service.list_shares_received_from(db, project_id)
    return {"shares": shares}


@router.post("")
async def grant_share(
    req: ShareGrantRequest,
    project_id: str = Path(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Grant another project read or read_write access to this project's memories."""
    await require_project_member(db, project_id, user, write=True)
    try:
        share = await sharing_service.grant_share(
            db,
            project_id,
            req.target_project_id,
            req.permission,
            actor_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"share": share}


@router.delete("/{target_project_id}")
async def revoke_share(
    target_project_id: str,
    project_id: str = Path(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a project's access to this project's memories."""
    await require_project_member(db, project_id, user, write=True)
    revoked = await sharing_service.revoke_share(db, project_id, target_project_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Share not found")
    return {"revoked": True}


@router.get("/{target_project_id}/check")
async def check_share(
    target_project_id: str,
    project_id: str = Path(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if this project has shared memories with target_project."""
    await require_project_member(db, project_id, user)
    share = await sharing_service.get_share(db, project_id, target_project_id)
    if not share:
        return {"shared": False, "permission": None}
    return {"shared": True, "permission": share["permission"]}