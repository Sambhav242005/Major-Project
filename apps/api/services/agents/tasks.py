"""Agent task helpers — get_task / list_tasks with trace."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Agent, AgentTask


async def get_task(
    db: AsyncSession,
    agent_id: str,
    task_id: str,
    project_id: str,
) -> dict | None:
    """Get agent task with trace."""
    stmt = (
        select(AgentTask)
        .join(Agent, Agent.id == AgentTask.agent_id)
        .where(
            AgentTask.id == uuid.UUID(task_id),
            AgentTask.agent_id == uuid.UUID(agent_id),
            Agent.project_id == uuid.UUID(project_id),
        )
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        return None

    return {
        "id": str(task.id),
        "agent_id": str(task.agent_id),
        "input": task.input,
        "output": task.output,
        "status": task.status,
        "trace": task.trace or [],
        "error": task.error,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


async def list_tasks(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    limit: int = 20,
) -> list[dict]:
    """List recent tasks for an agent."""
    stmt = (
        select(AgentTask)
        .join(Agent, Agent.id == AgentTask.agent_id)
        .where(
            AgentTask.agent_id == uuid.UUID(agent_id),
            Agent.project_id == uuid.UUID(project_id),
        )
        .order_by(AgentTask.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "agent_id": str(t.agent_id),
            "status": t.status,
            "output": t.output,
            "error": t.error,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in tasks
    ]
