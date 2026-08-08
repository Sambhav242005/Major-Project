"""Agents router — CRUD, run, task traces, memory, and checkpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.security import get_current_user, User
from core.deps import get_project_id
from db.session import get_db
from services import agents as agent_service
from services import memory as memory_service

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


class MemoryStoreRequest(BaseModel):
    memory_type: str  # working, episodic, semantic
    content: dict
    embedding: list[float] | None = None
    metadata: dict = {}
    ttl_hours: int | None = None


class CheckpointSaveRequest(BaseModel):
    state: dict
    task_id: str | None = None


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


@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str,
    req: AgentRunRequest = AgentRunRequest(),
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger agent execution (with memory hydration)."""
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
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent tasks for an agent."""
    tasks = await agent_service.list_tasks(db, agent_id, project_id)
    return {"tasks": tasks}


@router.get("/{agent_id}/tasks/{task_id}")
async def get_agent_task(
    agent_id: str,
    task_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get agent task with trace."""
    task = await agent_service.get_task(db, agent_id, task_id, project_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}


# --- Memory endpoints ---


@router.get("/{agent_id}/memory")
async def list_memories(
    agent_id: str,
    memory_type: str | None = Query(None, description="Filter by type: working, episodic, semantic"),
    limit: int = Query(20, ge=1, le=100),
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List agent memories (scoped to project)."""
    memories = await memory_service.retrieve_memories(
        db, agent_id, project_id, memory_type=memory_type, limit=limit,
    )
    return {"memories": memories}


@router.post("/{agent_id}/memory")
async def store_memory(
    agent_id: str,
    req: MemoryStoreRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store a memory for an agent."""
    try:
        memory = await memory_service.store_memory(
            db, agent_id, project_id,
            memory_type=req.memory_type,
            content=req.content,
            embedding=req.embedding,
            metadata=req.metadata,
            ttl_hours=req.ttl_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"memory": memory}


@router.delete("/{agent_id}/memory/{memory_id}")
async def delete_memory(
    agent_id: str,
    memory_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific memory."""
    deleted = await memory_service.delete_memory(db, memory_id, agent_id, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True}


@router.get("/{agent_id}/memory/search")
async def search_memory(
    agent_id: str,
    q: str = Query(..., description="Search query (will be embedded)"),
    memory_type: str | None = Query(None),
    limit: int = Query(5, ge=1, le=20),
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search agent memories by semantic similarity.

    Note: In production, use a real embedding model.
    Currently uses a simple hash-based pseudo-embedding for demo purposes.
    """
    # Simple hash-based embedding for demo (replace with real model in prod)
    query_embedding = _simple_embedding(q)
    results = await memory_service.search_memories(
        db, agent_id, project_id, query_embedding,
        memory_type=memory_type, limit=limit,
    )
    return {"results": results}


# --- Checkpoint endpoints ---


@router.post("/{agent_id}/checkpoint")
async def save_checkpoint(
    agent_id: str,
    req: CheckpointSaveRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save agent checkpoint for stop/resume."""
    checkpoint = await memory_service.save_checkpoint(
        db, agent_id, req.task_id, req.state,
    )
    return {"checkpoint": checkpoint}


@router.get("/{agent_id}/checkpoint")
async def get_checkpoint(
    agent_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get latest checkpoint for an agent."""
    checkpoint = await memory_service.load_latest_checkpoint(db, agent_id)
    if not checkpoint:
        return {"checkpoint": None}
    return {"checkpoint": checkpoint}


@router.get("/{agent_id}/context")
async def get_agent_context(
    agent_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full agent memory context (for debugging/inspection)."""
    context = await memory_service.hydrate_agent_context(db, agent_id, project_id)
    return {"context": context}


def _simple_embedding(text: str) -> list[float]:
    """Hash-based pseudo-embedding for demo. Replace with real model in prod."""
    import hashlib
    h = hashlib.sha256(text.encode()).digest()
    # Convert bytes to float list (0.0-1.0 range)
    return [b / 255.0 for b in h]
