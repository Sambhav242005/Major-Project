"""Agents router — CRUD, run, and task trace endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.security import get_current_user, User
from db.session import get_db
from services import agents as agent_service

router = APIRouter()


class AgentCreateRequest(BaseModel):
    name: str
    type: str
    config: dict = {}


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    config: dict | None = None
    status: str | None = None


class AgentRunRequest(BaseModel):
    input: dict = {}


@router.get("/types")
async def list_agent_types(user: User = Depends(get_current_user)):
    """List available agent types."""
    return {"types": agent_service.list_agent_types()}


@router.get("")
async def list_agents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all agents for the current project."""
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    agents = await agent_service.list_agents(db, project_id)
    return {"agents": agents}


@router.post("")
async def create_agent(
    req: AgentCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new agent."""
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder

    # Validate agent type
    available_types = [t["type"] for t in agent_service.list_agent_types()]
    if req.type not in available_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent type '{req.type}'. Available: {available_types}",
        )

    agent = await agent_service.create_agent(
        db=db, user=user, project_id=project_id,
        name=req.name, agent_type=req.type, config=req.config,
    )
    return {"agent": agent}


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single agent."""
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    agent = await agent_service.get_agent(db, agent_id, project_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"agent": agent}


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    req: AgentUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an agent."""
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    agent = await agent_service.update_agent(
        db=db, agent_id=agent_id, project_id=project_id,
        name=req.name, config=req.config, status=req.status,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"agent": agent}


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an agent."""
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    deleted = await agent_service.delete_agent(db, agent_id, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"deleted": True}


@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str,
    req: AgentRunRequest = AgentRunRequest(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger agent execution."""
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    result = await agent_service.run_agent(
        db=db, agent_id=agent_id, project_id=project_id,
        input_data=req.input,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{agent_id}/tasks")
async def list_agent_tasks(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent tasks for an agent."""
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    tasks = await agent_service.list_tasks(db, agent_id, project_id)
    return {"tasks": tasks}


@router.get("/{agent_id}/tasks/{task_id}")
async def get_agent_task(
    agent_id: str,
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get agent task with trace."""
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    task = await agent_service.get_task(db, agent_id, task_id, project_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}
