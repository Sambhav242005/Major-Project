"""Cross-project memory sharing service.

Allows projects to share agent memories with controlled permissions:
- read: target project can read source project's memories
- read_write: target project can read and write to source project's memories
"""

import uuid
from datetime import datetime

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ProjectMemoryShare, AgentMemory


# --- Share management ---


async def grant_share(
    db: AsyncSession,
    source_project_id: str,
    target_project_id: str,
    permission: str = "read",
) -> dict:
    """Grant a project access to another project's memories.

    Args:
        source_project_id: Project whose memories are being shared
        target_project_id: Project that gets access
        permission: 'read' or 'read_write'
    """
    if permission not in ("read", "read_write"):
        raise ValueError(f"Invalid permission: {permission}. Use 'read' or 'read_write'.")
    if source_project_id == target_project_id:
        raise ValueError("Cannot share a project with itself.")

    # Check if share already exists
    existing = await get_share(db, source_project_id, target_project_id)
    if existing:
        # Update permission
        stmt = select(ProjectMemoryShare).where(
            ProjectMemoryShare.source_project_id == uuid.UUID(source_project_id),
            ProjectMemoryShare.target_project_id == uuid.UUID(target_project_id),
        )
        result = await db.execute(stmt)
        share = result.scalar_one()
        share.permission = permission
        await db.flush()
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


# --- Memory retrieval with sharing ---


async def retrieve_shared_memories(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    memory_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Retrieve memories from shared projects.

    Returns memories from other projects that have shared with this project.
    Marked with 'shared_from_project' in metadata.

    Note: Memories belong to the project, not to a specific agent.
    We use retrieve_project_memories (project-scoped) instead of
    retrieve_memories (agent-scoped) so cross-project sharing works
    regardless of which agent created the memory.
    """
    shared_project_ids = await get_shared_project_ids(db, project_id)
    if not shared_project_ids:
        return []

    from services.memory import retrieve_project_memories

    all_shared = []
    per_project_limit = max(1, limit // len(shared_project_ids))

    for shared_pid in shared_project_ids:
        memories = await retrieve_project_memories(
            db, shared_pid,
            memory_type=memory_type,
            limit=per_project_limit,
        )
        for m in memories:
            m["shared_from_project"] = shared_pid
        all_shared.extend(memories)

    # Sort by created_at desc and apply limit
    all_shared.sort(key=lambda x: x["created_at"], reverse=True)
    return all_shared[:limit]


def _share_to_dict(share: ProjectMemoryShare) -> dict:
    return {
        "id": str(share.id),
        "source_project_id": str(share.source_project_id),
        "target_project_id": str(share.target_project_id),
        "permission": share.permission,
        "created_at": share.created_at.isoformat() if share.created_at else None,
    }
