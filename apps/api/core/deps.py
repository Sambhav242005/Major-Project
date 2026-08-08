"""Shared FastAPI dependencies for project context resolution.

Replaces hardcoded placeholder project_id across all routers.
Resolves project_id from user's memberships in the database.
"""

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import User, get_current_user
from db.session import get_db
from db.models import ProjectMember


async def get_project_id(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    project_id: str | None = Query(None, description="Project ID"),
) -> str:
    """Resolve project_id from query param or user's default project.

    Priority:
      1. Explicit ?project_id= query param (client specifies which project)
      2. Auto-detect if user has exactly one project
      3. 400 error if user has multiple projects and none specified
      4. 404 error if user has no projects
    """
    if project_id:
        # Verify user is a member of this project
        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this project",
            )
        return project_id

    # Auto-detect: find all projects user belongs to
    stmt = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    result = await db.execute(stmt)
    project_ids = [row[0] for row in result.all()]

    if len(project_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No projects found. Create a project first.",
        )
    if len(project_ids) == 1:
        return str(project_ids[0])

    # Multiple projects — client must specify which one
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"User belongs to {len(project_ids)} projects. Pass ?project_id= to specify which one.",
    )
