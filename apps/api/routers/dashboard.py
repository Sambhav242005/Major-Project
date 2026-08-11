"""Dashboard router — summary stats, activity feed, pipeline health."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from db.session import get_db
from services.dashboard import get_summary

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    project_id: str = Depends(get_project_id),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard summary stats for the current project."""
    try:
        summary = await get_summary(db, project_id)
        return {"status": "ok", "data": summary}
    except Exception as e:
        # Never leak internal details — log them, return a clean 500.
        import logging
        logging.getLogger(__name__).exception("Dashboard summary failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard summary",
        )
