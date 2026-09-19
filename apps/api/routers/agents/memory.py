"""Agent memory and checkpoint endpoints."""

from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import assert_agent_in_project, get_project_id
from core.security import User, get_current_user
from db.session import get_db
from services import memory as memory_service
from services.embeddings import embed_text

from . import router
from .schemas import CheckpointSaveRequest, MemoryStoreRequest


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
    """Store a memory for an agent. Auto-generates embedding if not provided."""
    try:
        embedding = req.embedding
        if not embedding:
            text = " ".join(str(v) for v in req.content.values())
            embedding = await embed_text(text)
        memory = await memory_service.store_memory(
            db, agent_id, project_id,
            memory_type=req.memory_type,
            content=req.content,
            embedding=embedding,
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
    """Search agent memories by semantic similarity using Ollama embeddings."""
    query_embedding = await embed_text(q)
    results = await memory_service.search_memories(
        db, agent_id, project_id, query_embedding,
        memory_type=memory_type, limit=limit,
    )
    return {"results": results}


@router.post("/{agent_id}/checkpoint")
async def save_checkpoint(
    agent_id: str,
    req: CheckpointSaveRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save agent checkpoint for stop/resume."""
    await assert_agent_in_project(db, agent_id, project_id)
    checkpoint = await memory_service.save_checkpoint(db, agent_id, req.task_id, req.state)
    return {"checkpoint": checkpoint}


@router.get("/{agent_id}/checkpoint")
async def get_checkpoint(
    agent_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get latest checkpoint for an agent."""
    await assert_agent_in_project(db, agent_id, project_id)
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
    await assert_agent_in_project(db, agent_id, project_id)
    context = await memory_service.hydrate_agent_context(db, agent_id, project_id)
    return {"context": context}
