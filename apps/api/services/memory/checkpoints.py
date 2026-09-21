"""Memory checkpoints — save and load agent state snapshots."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentCheckpoint


async def save_checkpoint(
    db: AsyncSession,
    agent_id: str,
    task_id: str | None,
    state: dict,
) -> dict:
    """Save an agent checkpoint (working memory snapshot) for resume later."""
    checkpoint = AgentCheckpoint(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(agent_id),
        task_id=uuid.UUID(task_id) if task_id else None,
        state=state,
        created_at=datetime.now(timezone.utc),
    )
    db.add(checkpoint)
    await db.flush()

    return {
        "id": str(checkpoint.id),
        "agent_id": str(checkpoint.agent_id),
        "state": checkpoint.state,
        "created_at": checkpoint.created_at.isoformat(),
    }


async def load_latest_checkpoint(
    db: AsyncSession,
    agent_id: str,
) -> dict | None:
    """Load the most recent checkpoint for an agent."""
    stmt = (
        select(AgentCheckpoint)
        .where(AgentCheckpoint.agent_id == uuid.UUID(agent_id))
        .order_by(AgentCheckpoint.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    checkpoint = result.scalar_one_or_none()
    if not checkpoint:
        return None

    return {
        "id": str(checkpoint.id),
        "agent_id": str(checkpoint.agent_id),
        "task_id": str(checkpoint.task_id) if checkpoint.task_id else None,
        "state": checkpoint.state,
        "created_at": checkpoint.created_at.isoformat(),
    }
