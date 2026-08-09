"""Project memory sharing router — grant/revoke/list cross-project memory access."""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.security import get_current_user, User
from db.session import get_db
from services import sharing as sharing_service

router = APIRouter()


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
    shares = await sharing_service.list_shares_given_to(db, project_id)
    return {"shares": shares}


@router.get("/received")
async def list_received_shares(
    project_id: str = Path(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all shares other projects have given to this project."""
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
    try:
        share = await sharing_service.grant_share(
            db, project_id, req.target_project_id, req.permission,
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
    share = await sharing_service.get_share(db, project_id, target_project_id)
    if not share:
        return {"shared": False, "permission": None}
    return {"shared": True, "permission": share["permission"]}
