"""Projects router — list, create, and rename projects for the current user.

The rest of the API resolves an active project via get_project_id (explicit
?project_id= param, auto-detect for single-project users, or auto-create for
new users). This router is the management surface for that set of projects.
"""

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import _user_uuid
from core.security import get_current_user, User
from db.session import get_db
from db.models import Agent, ChatSession, Document, Entity, Project, ProjectMember

router = APIRouter()


class ProjectOut(BaseModel):
    id: str
    name: str
    role: str
    created_at: str | None = None
    member_count: int = 0
    document_count: int = 0
    entity_count: int = 0
    chat_count: int = 0
    agent_count: int = 0


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class ProjectRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all projects the current user is a member of."""
    uid = _user_uuid(user.id)

    rows = await db.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == uid)
        .order_by(Project.created_at.desc())
    )
    projects = [(p, role) for p, role in rows.all()]
    if not projects:
        return []

    project_ids = [p.id for p, _ in projects]

    counts = await db.execute(
        select(
            Document.project_id, func.count(Document.id)
        ).where(Document.project_id.in_(project_ids)).group_by(Document.project_id)
    )
    doc_counts = dict(counts.all())

    entity_counts = dict(
        (await db.execute(
            select(Entity.project_id, func.count(Entity.id))
            .where(Entity.project_id.in_(project_ids))
            .group_by(Entity.project_id)
        )).all()
    )

    chat_counts = dict(
        (await db.execute(
            select(ChatSession.project_id, func.count(ChatSession.id))
            .where(ChatSession.project_id.in_(project_ids))
            .group_by(ChatSession.project_id)
        )).all()
    )

    agent_counts = dict(
        (await db.execute(
            select(Agent.project_id, func.count(Agent.id))
            .where(Agent.project_id.in_(project_ids))
            .group_by(Agent.project_id)
        )).all()
    )

    member_counts = dict(
        (await db.execute(
            select(ProjectMember.project_id, func.count(ProjectMember.user_id))
            .where(ProjectMember.project_id.in_(project_ids))
            .group_by(ProjectMember.project_id)
        )).all()
    )

    return [
        ProjectOut(
            id=str(p.id),
            name=p.name,
            role=role,
            created_at=p.created_at.isoformat() if p.created_at else None,
            member_count=member_counts.get(p.id, 0),
            document_count=doc_counts.get(p.id, 0),
            entity_count=entity_counts.get(p.id, 0),
            chat_count=chat_counts.get(p.id, 0),
            agent_count=agent_counts.get(p.id, 0),
        )
        for p, role in projects
    ]


@router.post("", status_code=201, response_model=ProjectOut)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project owned by the current user."""
    project = Project(name=payload.name.strip(), owner_id=_user_uuid(user.id))
    db.add(project)
    await db.flush()

    member = ProjectMember(
        project_id=project.id,
        user_id=_user_uuid(user.id),
        role="editor",
    )
    db.add(member)
    await db.commit()

    return ProjectOut(
        id=str(project.id),
        name=project.name,
        role="editor",
        created_at=project.created_at.isoformat() if project.created_at else None,
        member_count=1,
    )


@router.patch("/{project_id}", response_model=ProjectOut)
async def rename_project(
    project_id: str,
    payload: ProjectRename,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename a project the current user is a member of (editor or owner)."""
    try:
        proj_uuid = _uuid.UUID(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="Project not found")

    membership = (
        await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == proj_uuid,
                ProjectMember.user_id == _user_uuid(user.id),
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Project not found")
    if membership.role not in ("owner", "editor"):
        raise HTTPException(
            status_code=403,
            detail="Only owners/editors can rename this project",
        )

    project = await db.get(Project, proj_uuid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.name = payload.name.strip()
    await db.commit()

    return ProjectOut(
        id=str(project.id),
        name=project.name,
        role=membership.role,
        created_at=project.created_at.isoformat() if project.created_at else None,
        member_count=1,
    )
