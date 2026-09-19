"""Sharing permissions — grant, revoke, list, and checks."""

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ProjectMemoryShare
from services.audit import write_audit_log


def _share_to_dict(share: ProjectMemoryShare) -> dict:
    return {
        "id": str(share.id),
        "source_project_id": str(share.source_project_id),
        "target_project_id": str(share.target_project_id),
        "permission": share.permission,
        "created_at": share.created_at.isoformat() if share.created_at else None,
    }


async def get_share(
    db: AsyncSession,
    source_project_id: str,
    target_project_id: str,
) -> dict | None:
    """Check if a share exists between two projects."""
    stmt = select(ProjectMemoryShare).where(
        ProjectMemoryShare.source_project_id == uuid.UUID(source_project_id),
        ProjectMemoryShare.target_project_id == uuid.UUID(target_project_id),
    )
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()
    return _share_to_dict(share) if share else None


async def grant_share(
    db: AsyncSession,
    source_project_id: str,
    target_project_id: str,
    permission: str = "read",
    actor_id=None,
) -> dict:
    """Grant a project access to another project's memories."""
    if permission not in ("read", "read_write"):
        raise ValueError(f"Invalid permission: {permission}. Use 'read' or 'read_write'.")
    if source_project_id == target_project_id:
        raise ValueError("Cannot share a project with itself.")

    existing = await get_share(db, source_project_id, target_project_id)
    if existing:
        stmt = select(ProjectMemoryShare).where(
            ProjectMemoryShare.source_project_id == uuid.UUID(source_project_id),
            ProjectMemoryShare.target_project_id == uuid.UUID(target_project_id),
        )
        result = await db.execute(stmt)
        share = result.scalar_one()
        share.permission = permission
        await db.flush()
        await write_audit_log(
            db=db,
            project_id=uuid.UUID(source_project_id),
            actor_id=actor_id,
            action="share.granted",
            resource_type="project_share",
            resource_id=share.id,
            meta={
                "target_project_id": target_project_id,
                "permission": permission,
            },
        )
        return _share_to_dict(share)

    share = ProjectMemoryShare(
        id=uuid.uuid4(),
        source_project_id=uuid.UUID(source_project_id),
        target_project_id=uuid.UUID(target_project_id),
        permission=permission,
        created_at=datetime.utcnow(),
    )
    db.add(share)
    await db.flush()
    await write_audit_log(
        db=db,
        project_id=uuid.UUID(source_project_id),
        actor_id=actor_id,
        action="share.granted",
        resource_type="project_share",
        resource_id=share.id,
        meta={
            "target_project_id": target_project_id,
            "permission": permission,
        },
    )
    return _share_to_dict(share)


async def revoke_share(
    db: AsyncSession,
    source_project_id: str,
    target_project_id: str,
) -> bool:
    """Revoke a project's access to another project's memories."""
    stmt = delete(ProjectMemoryShare).where(
        ProjectMemoryShare.source_project_id == uuid.UUID(source_project_id),
        ProjectMemoryShare.target_project_id == uuid.UUID(target_project_id),
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount > 0


async def list_shares_given_to(
    db: AsyncSession,
    source_project_id: str,
) -> list[dict]:
    """List all projects that source_project has shared memories with."""
    stmt = (
        select(ProjectMemoryShare)
        .where(ProjectMemoryShare.source_project_id == uuid.UUID(source_project_id))
        .order_by(ProjectMemoryShare.created_at.desc())
    )
    result = await db.execute(stmt)
    shares = result.scalars().all()
    return [_share_to_dict(s) for s in shares]


async def list_shares_received_from(
    db: AsyncSession,
    target_project_id: str,
) -> list[dict]:
    """List all projects that have shared their memories with target_project."""
    stmt = (
        select(ProjectMemoryShare)
        .where(ProjectMemoryShare.target_project_id == uuid.UUID(target_project_id))
        .order_by(ProjectMemoryShare.created_at.desc())
    )
    result = await db.execute(stmt)
    shares = result.scalars().all()
    return [_share_to_dict(s) for s in shares]


async def get_shared_project_ids(
    db: AsyncSession,
    project_id: str,
) -> list[str]:
    """Get all project IDs whose memories are readable by this project."""
    stmt = (
        select(ProjectMemoryShare.source_project_id)
        .where(ProjectMemoryShare.target_project_id == uuid.UUID(project_id))
    )
    result = await db.execute(stmt)
    return [str(row[0]) for row in result.all()]


async def can_write_to_project(
    db: AsyncSession,
    source_project_id: str,
    target_project_id: str,
) -> bool:
    """Check if source_project has write permission on target_project's memories."""
    share = await get_share(db, target_project_id, source_project_id)
    if not share:
        return False
    return share["permission"] == "read_write"
