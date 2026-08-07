"""Dashboard router — summary stats, activity feed, pipeline health."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user, User
from db.session import get_db
from services.dashboard import get_summary

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard summary stats for the current project."""
    # TODO: Get project_id from request/header (Phase 3 step: add project context)
    project_id = "00000000-0000-0000-0000-000000000001"

    try:
        summary = await get_summary(db, project_id)
        return {"status": "ok", "data": summary}
    except Exception as e:
        return {"status": "error", "error": str(e)}
