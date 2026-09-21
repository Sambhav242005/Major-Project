"""Agent execution endpoints (run, tasks, SSE stream)."""

import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.rate_limit import limiter
from core.security import User, get_current_user
from core.sse import queue_sse_stream
from core.task_queue import start_agent_task, subscribe_task, unsubscribe_task
from db.models import AgentTask
from db.session import async_session_factory, get_db
from services import agents as agent_service

from . import router
from .schemas import AgentRunRequest


@router.post("/{agent_id}/run")
@limiter.limit("30/minute")
async def run_agent(
    request: Request,
    response: Response,
    agent_id: str,
    req: AgentRunRequest = AgentRunRequest(),
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger agent execution (non-blocking). Returns task_id immediately."""
    agent = await agent_service.get_agent(db, agent_id, project_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    task_id = str(uuid.uuid4())
    task = AgentTask(
        id=uuid.UUID(task_id),
        agent_id=uuid.UUID(agent_id),
        input=req.input,
        status="running",
        trace=[],
        started_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()
    await db.commit()

    try:
        start_agent_task(
            session_factory=async_session_factory,
            agent_id=agent_id,
            task_id=task_id,
            project_id=project_id,
            input_data=req.input,
        )
    except Exception as e:
        task.status = "failed"
        task.error = f"Failed to start: {e}"
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {e}")

    return {
        "task_id": task_id,
        "agent_id": agent_id,
        "status": "running",
        "message": "Agent execution started. Poll /agents/{id}/tasks/{task_id} or subscribe to SSE.",
    }


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


@router.get("/{agent_id}/tasks/{task_id}/stream")
async def stream_agent_task(
    agent_id: str,
    task_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
):
    """SSE stream for real-time agent task progress."""
    return await queue_sse_stream(
        subscribe=lambda: subscribe_task(task_id),
        unsubscribe=lambda q: unsubscribe_task(task_id, q),
    )
