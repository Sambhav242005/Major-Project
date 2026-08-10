"""In-memory task queue for background agent execution.

Provides non-blocking agent runs: API returns immediately with task_id,
background worker executes the agent, stores results in DB.
"""

import asyncio
import json
import logging
import uuid
from collections import deque
from datetime import datetime

from sqlalchemy import select

from db.models import Agent, AgentTask
from pipelines.agent_pipeline import execute_agent
from services.memory import (
    store_memory,
    hydrate_agent_context,
    format_memory_context,
    cleanup_expired_memories,
    save_checkpoint,
)

logger = logging.getLogger(__name__)

# In-memory task status tracker (for SSE streams)
# Events per task are capped to bound memory; subscriber lists are cleaned
# on stream close and dropped on task completion.
_task_events: dict[str, deque] = {}
_task_subscribers: dict[str, list[asyncio.Queue]] = {}

# Strong references to running background tasks so the event loop never
# garbage-collects a task mid-run ("Task was destroyed but it is pending").
_running_tasks: set[asyncio.Task] = set()

MAX_EVENTS_PER_TASK = 200


def _publish_event(task_id: str, event: dict):
    """Publish a trace event to all SSE subscribers of this task."""
    if task_id not in _task_events:
        _task_events[task_id] = deque(maxlen=MAX_EVENTS_PER_TASK)
    _task_events[task_id].append(event)

    if task_id in _task_subscribers:
        dead = []
        for q in _task_subscribers[task_id]:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _task_subscribers[task_id].remove(q)


def _drop_task_events(task_id: str):
    """Release the event buffer + subscribers for a finished task."""
    _task_events.pop(task_id, None)
    _task_subscribers.pop(task_id, None)


def subscribe_task(task_id: str) -> asyncio.Queue:
    """Subscribe to live events for a task. Returns an asyncio.Queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    if task_id not in _task_subscribers:
        _task_subscribers[task_id] = []
    _task_subscribers[task_id].append(q)
    for event in _task_events.get(task_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            break
    return q


def unsubscribe_task(task_id: str, q: asyncio.Queue):
    """Remove an SSE subscriber."""
    if task_id in _task_subscribers:
        _task_subscribers[task_id] = [x for x in _task_subscribers[task_id] if x is not q]


async def _run_agent_background(session_factory, agent_id, task_id, project_id, input_data):
    """Background coroutine that executes an agent and updates DB."""
    db = session_factory()
    try:
        agent_result = await db.execute(
            select(Agent).where(Agent.id == uuid.UUID(agent_id))
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            _publish_event(task_id, {
                "step": "initialize", "status": "error",
                "error": "Agent not found",
                "timestamp": datetime.utcnow().isoformat(),
            })
            return

        await cleanup_expired_memories(db, agent_id, project_id)
        memory_context = await hydrate_agent_context(db, agent_id, project_id)
        memory_str = format_memory_context(memory_context)

        enriched_input = dict(input_data)
        if memory_str:
            enriched_input["_memory_context"] = memory_str

        # Hydrate skills into prompt
        from services.agents import _hydrate_skills
        skills_text = await _hydrate_skills(db, agent_id)
        if skills_text:
            enriched_input["_skills_context"] = skills_text

        trace = []
        final_output = None

        async for event in execute_agent(
            agent_type=agent.type,
            config=agent.config or {},
            input_data=enriched_input,
            db_session=db,
            project_id=project_id,
        ):
            trace.append(event)
            _publish_event(task_id, event)

            if event.get("status") == "completed" and event.get("step") == "post_process":
                final_output = event.get("output")
            elif event.get("status") == "error":
                task_result = await db.execute(
                    select(AgentTask).where(AgentTask.id == uuid.UUID(task_id))
                )
                task = task_result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error = event.get("error", "Unknown error")
                    task.trace = trace
                    task.completed_at = datetime.utcnow()
                    await db.flush()

                await save_checkpoint(
                    db, agent_id, task_id,
                    state={"last_input": input_data, "error": event.get("error"), "trace_step": len(trace)},
                )
                await db.commit()
                return

        # Success
        task_result = await db.execute(
            select(AgentTask).where(AgentTask.id == uuid.UUID(task_id))
        )
        task = task_result.scalar_one_or_none()
        if task:
            task.status = "completed"
            task.output = final_output
            task.trace = trace
            task.completed_at = datetime.utcnow()

        agent.last_active_at = datetime.utcnow()

        if final_output:
            await store_memory(
                db, agent_id, project_id,
                memory_type="episodic",
                content={
                    "task_id": task_id,
                    "input_summary": json.dumps(input_data, default=str)[:500],
                    "output_summary": json.dumps(final_output, default=str)[:500],
                    "agent_type": agent.type,
                },
            )

        await db.commit()

        _publish_event(task_id, {
            "step": "complete", "status": "completed",
            "output": final_output,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Fire agent.completed webhook
        try:
            from services.webhooks import fire_event
            await fire_event(
                db=db,
                project_id=project_id,
                event_type="agent.completed",
                payload={
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "status": "completed",
                    "output_summary": json.dumps(final_output, default=str)[:500] if final_output else None,
                },
            )
            await db.commit()
        except Exception:
            logger.warning("Failed to fire agent.completed webhook")

    except Exception as e:
        logger.exception(f"Background agent execution failed: {e}")
        try:
            task_result = await db.execute(
                select(AgentTask).where(AgentTask.id == uuid.UUID(task_id))
            )
            task = task_result.scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error = str(e)
                task.completed_at = datetime.utcnow()
                await db.commit()
        except Exception:
            logger.exception("Failed to update task status after error")

        _publish_event(task_id, {
            "step": "execution", "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Fire agent.failed webhook
        try:
            from services.webhooks import fire_event
            await fire_event(
                db=db,
                project_id=project_id,
                event_type="agent.failed",
                payload={
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "error": str(e)[:500],
                },
            )
            await db.commit()
        except Exception:
            pass

        try:
            await save_checkpoint(db, agent_id, task_id, state={"last_input": input_data, "error": str(e)})
            await db.commit()
        except Exception:
            pass
    finally:
        await db.close()


def start_agent_task(session_factory, agent_id, task_id, project_id, input_data):
    """Launch agent execution in background. Non-blocking.

    Holds a strong reference to the task so the event loop doesn't
    garbage-collect it mid-run, and releases the event buffer on exit.
    """
    task = asyncio.create_task(
        _run_agent_background(session_factory, agent_id, task_id, project_id, input_data)
    )
    _running_tasks.add(task)

    def _done(t: asyncio.Task):
        _running_tasks.discard(t)
        _drop_task_events(task_id)

    task.add_done_callback(_done)
