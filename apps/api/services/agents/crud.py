"""Agent CRUD — list/get/create/update/delete and type listing."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import User
from db.models import Agent
from pipelines.agent_pipeline import AGENT_TYPES, get_agent_type_info


async def list_agents(db: AsyncSession, project_id: str) -> list[dict]:
    """List all agents for a project."""
    stmt = (
        select(Agent)
        .where(Agent.project_id == uuid.UUID(project_id))
        .order_by(Agent.created_at.desc())
    )
    result = await db.execute(stmt)
    agents = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "name": a.name,
            "type": a.type,
            "config": a.config or {},
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in agents
    ]


async def get_agent(db: AsyncSession, agent_id: str, project_id: str) -> dict | None:
    """Get a single agent by ID."""
    stmt = select(Agent).where(
        Agent.id == uuid.UUID(agent_id),
        Agent.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        return None
    return {
        "id": str(agent.id),
        "name": agent.name,
        "type": agent.type,
        "config": agent.config or {},
        "status": agent.status,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


async def create_agent(
    db: AsyncSession,
    user: User,
    project_id: str,
    name: str,
    agent_type: str,
    config: dict = {},
) -> dict:
    """Create a new agent."""
    type_info = get_agent_type_info(agent_type)

    agent = Agent(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_id),
        owner_id=uuid.UUID(user.id),
        name=name,
        type=agent_type,
        config={**type_info, **config},
        status="active",
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    await db.flush()

    return {
        "id": str(agent.id),
        "name": agent.name,
        "type": agent.type,
        "config": agent.config,
        "status": agent.status,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


async def update_agent(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    name: str | None = None,
    config: dict | None = None,
    status: str | None = None,
) -> dict | None:
    """Update an agent."""
    stmt = select(Agent).where(
        Agent.id == uuid.UUID(agent_id),
        Agent.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        return None

    if name is not None:
        agent.name = name
    if config is not None:
        agent.config = {**(agent.config or {}), **config}
    if status is not None:
        agent.status = status

    await db.flush()

    return {
        "id": str(agent.id),
        "name": agent.name,
        "type": agent.type,
        "config": agent.config,
        "status": agent.status,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


async def delete_agent(db: AsyncSession, agent_id: str, project_id: str) -> bool:
    """Delete an agent."""
    stmt = select(Agent).where(
        Agent.id == uuid.UUID(agent_id),
        Agent.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        return False
    await db.delete(agent)
    await db.flush()
    return True


def list_agent_types() -> list[dict]:
    """List available agent types with info."""
    return [
        {
            "type": k,
            "name": v["name"],
            "description": v["description"],
        }
        for k, v in AGENT_TYPES.items()
    ]
