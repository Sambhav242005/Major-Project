"""Shared FastAPI dependencies for project context resolution.

Replaces hardcoded placeholder project_id across all routers.
Resolves project_id from user's memberships in the database.
Auto-creates a default project for new users.
"""

import uuid as _uuid

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import User, get_current_user
from db.session import get_db
from db.models import Profile, Project, ProjectMember

# Deterministic namespace for deriving UUIDs from string user IDs
_NS = _uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _user_uuid(user_id: str) -> _uuid.UUID:
    """Deterministic UUID from any string user ID."""
    return _uuid.uuid5(_NS, user_id)


async def _ensure_user_and_project(db: AsyncSession, user: User) -> _uuid.UUID:
    """Ensure user has a profile and default project. Returns project UUID."""
    profile_uuid = _user_uuid(user.id)

    # Upsert profile
    profile = (await db.execute(select(Profile).where(Profile.id == profile_uuid))).scalar_one_or_none()
    if not profile:
        profile = Profile(id=profile_uuid, full_name=user.email or user.id)
        db.add(profile)
        await db.flush()

    # Find existing project
    project = (
        await db.execute(
            select(Project).where(Project.owner_id == profile_uuid).limit(1)
        )
    ).scalar_one_or_none()

    if project:
        return _uuid.UUID(str(project.id))

    # Create default project
    project = Project(
        name="My Knowledge Base",
        owner_id=profile_uuid,
    )
    db.add(project)
    await db.flush()

    member = ProjectMember(
        project_id=project.id,
        user_id=profile_uuid,
        role="editor",
    )
    db.add(member)
    await db.flush()

    return _uuid.UUID(str(project.id))


async def get_project_id(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    project_id: str | None = Query(None, description="Project ID"),
) -> str:
    """Resolve project_id from query param or user's default project.

    Priority:
      1. Explicit ?project_id= query param (client specifies which project)
      2. Auto-detect if user has exactly one project
      3. Auto-create default project if user has none
      4. 400 error if user has multiple projects and none specified
    """
    if project_id:
        # Reject non-UUID project_ids with a clean 400 (not a 500 from uuid.UUID)
        try:
            project_uuid = _uuid.UUID(project_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid project_id: must be a UUID",
            )

        # Verify user is a member of this project
        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_uuid,
            ProjectMember.user_id == _user_uuid(user.id),
        )
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this project",
            )
        return project_id

    # Auto-detect: find all projects user belongs to
    stmt = select(ProjectMember.project_id).where(ProjectMember.user_id == _user_uuid(user.id))
    result = await db.execute(stmt)
    project_ids = [row[0] for row in result.all()]

    if len(project_ids) == 0:
        # Auto-create default project for new users
        proj_uuid = await _ensure_user_and_project(db, user)
        return str(proj_uuid)

    if len(project_ids) == 1:
        return str(project_ids[0])

    # Multiple projects — client must specify which one
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"User belongs to {len(project_ids)} projects. Pass ?project_id= to specify which one.",
    )


async def assert_agent_in_project(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
) -> None:
    """Verify an agent belongs to the resolved project.

    Returns silently on success; raises 404 otherwise. Uses 404 (not 403)
    so a caller can't probe for the existence of agents in other projects.
    Also normalises a non-UUID agent_id to 404 instead of a 500.
    """
    from db.models import Agent

    try:
        agent_uuid = _uuid.UUID(agent_id)
        proj_uuid = _uuid.UUID(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    stmt = select(Agent.project_id).where(Agent.id == agent_uuid)
    result = await db.execute(stmt)
    row = result.first()
    if row is None or row[0] != proj_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
