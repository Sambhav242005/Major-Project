"""Agents CRUD endpoints."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.security import User, get_current_user
from db.session import get_db
from services import agents as agent_service

from . import router
from .schemas import AgentCreateRequest, AgentUpdateRequest


@router.get("/types")
async def list_agent_types(user: User = Depends(get_current_user)):
    """List available agent types."""
    return {"types": agent_service.list_agent_types()}


@router.get("")
async def list_agents(
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all agents for the current project."""
    agents = await agent_service.list_agents(db, project_id)
    return {"agents": agents}


@router.post("")
async def create_agent(
    req: AgentCreateRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new agent."""
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
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single agent."""
    agent = await agent_service.get_agent(db, agent_id, project_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"agent": agent}


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    req: AgentUpdateRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an agent."""
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
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an agent."""
    deleted = await agent_service.delete_agent(db, agent_id, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"deleted": True}
