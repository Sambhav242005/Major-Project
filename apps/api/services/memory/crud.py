"""Memory CRUD — store, retrieve, delete, and project-scoped retrieval."""

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentMemory


async def store_memory(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    memory_type: str,
    content: dict,
    embedding: list[float] | None = None,
    metadata: dict | None = None,
    ttl_hours: int | None = None,
) -> dict:
    """Store a memory for an agent."""
    if memory_type not in ("working", "episodic", "semantic"):
        raise ValueError(f"Invalid memory_type: {memory_type}")

    now = datetime.utcnow()
    expires_at = None
    if memory_type == "working":
        expires_at = now + timedelta(hours=ttl_hours or 24)
    elif ttl_hours:
        expires_at = now + timedelta(hours=ttl_hours)

    memory = AgentMemory(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(agent_id),
        project_id=uuid.UUID(project_id),
        memory_type=memory_type,
        content=content,
        embedding=json.dumps(embedding) if embedding else None,
        metadata_=metadata or {},
        created_at=now,
        expires_at=expires_at,
    )
    db.add(memory)
    await db.flush()

    return {
        "id": str(memory.id),
        "memory_type": memory.memory_type,
        "content": memory.content,
        "created_at": memory.created_at.isoformat(),
        "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
    }


async def retrieve_memories(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    memory_type: str | None = None,
    limit: int = 20,
    include_expired: bool = False,
) -> list[dict]:
    """Retrieve memories for an agent, optionally filtered by type."""
    conditions = [
        AgentMemory.agent_id == uuid.UUID(agent_id),
        AgentMemory.project_id == uuid.UUID(project_id),
    ]
    if memory_type:
        conditions.append(AgentMemory.memory_type == memory_type)
    if not include_expired:
        conditions.append(
            (AgentMemory.expires_at.is_(None)) | (AgentMemory.expires_at > datetime.utcnow())
        )

    stmt = (
        select(AgentMemory)
        .where(and_(*conditions))
        .order_by(AgentMemory.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    memories = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "content": m.content,
            "metadata": m.metadata_ or {},
            "created_at": m.created_at.isoformat(),
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        }
        for m in memories
    ]


async def delete_memory(db: AsyncSession, memory_id: str, agent_id: str, project_id: str) -> bool:
    """Delete a specific memory. Verifies ownership."""
    stmt = select(AgentMemory).where(
        AgentMemory.id == uuid.UUID(memory_id),
        AgentMemory.agent_id == uuid.UUID(agent_id),
        AgentMemory.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if not memory:
        return False
    await db.delete(memory)
    await db.flush()
    return True


async def cleanup_expired_memories(db: AsyncSession, agent_id: str, project_id: str) -> int:
    """Delete expired working memories. Returns count deleted."""
    stmt = delete(AgentMemory).where(
        AgentMemory.agent_id == uuid.UUID(agent_id),
        AgentMemory.project_id == uuid.UUID(project_id),
        AgentMemory.memory_type == "working",
        AgentMemory.expires_at.isnot(None),
        AgentMemory.expires_at < datetime.utcnow(),
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount


async def retrieve_project_memories(
    db: AsyncSession,
    project_id: str,
    memory_type: str | None = None,
    limit: int = 20,
    include_expired: bool = False,
) -> list[dict]:
    """Retrieve memories for a project, regardless of agent."""
    conditions = [
        AgentMemory.project_id == uuid.UUID(project_id),
    ]
    if memory_type:
        conditions.append(AgentMemory.memory_type == memory_type)
    if not include_expired:
        conditions.append(
            (AgentMemory.expires_at.is_(None)) | (AgentMemory.expires_at > datetime.utcnow())
        )

    stmt = (
        select(AgentMemory)
        .where(and_(*conditions))
        .order_by(AgentMemory.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    memories = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "content": m.content,
            "metadata": m.metadata_ or {},
            "created_at": m.created_at.isoformat(),
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        }
        for m in memories
    ]
