"""Agent service — CRUD and execution with LangGraph traces."""

import uuid
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import User
from db.models import Agent, AgentTask
from pipelines.agent_pipeline import execute_agent, get_agent_type_info, AGENT_TYPES


async def list_agents(db: AsyncSession, project_id: str) -> list[dict]:
    """List all agents for a project."""
    stmt = (
        select(Agent)
        .where(Agent.project_id == project_id)
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
        Agent.project_id == project_id,
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
        Agent.project_id == project_id,
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
        Agent.project_id == project_id,
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        return False
    await db.delete(agent)
    await db.flush()
    return True


async def run_agent(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    input_data: dict = {},
) -> dict:
    """Trigger agent execution. Returns task_id for polling."""
    # Verify agent exists
    agent_stmt = select(Agent).where(
        Agent.id == uuid.UUID(agent_id),
        Agent.project_id == project_id,
    )
    agent_result = await db.execute(agent_stmt)
    agent = agent_result.scalar_one_or_none()
    if not agent:
        return {"error": "Agent not found"}

    # Create task record
    task = AgentTask(
        id=uuid.uuid4(),
        agent_id=agent.id,
        input=input_data,
        status="running",
        trace=[],
        started_at=datetime.utcnow(),
    )
    db.add(task)
    await db.flush()

    # Execute agent and collect trace
    trace = []
    final_output = None

    try:
        async for event in execute_agent(
            agent_type=agent.type,
            config=agent.config or {},
            input_data=input_data,
        ):
            trace.append(event)
            if event.get("status") == "completed" and event.get("step") == "post_process":
                final_output = event.get("output")
            elif event.get("status") == "error":
                task.status = "failed"
                task.error = event.get("error", "Unknown error")
                break
        else:
            task.status = "completed"
            task.output = final_output

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        trace.append({
            "step": "execution",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        })

    task.trace = trace
    task.completed_at = datetime.utcnow()
    await db.flush()

    return {
        "task_id": str(task.id),
        "agent_id": str(agent.id),
        "status": task.status,
        "output": task.output,
        "error": task.error,
    }


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
            Agent.project_id == project_id,
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
            Agent.project_id == project_id,
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
