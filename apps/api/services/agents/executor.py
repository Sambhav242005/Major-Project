"""Agent executor — run_agent with memory hydration and trace persistence."""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Agent, AgentSkill, AgentTask
from pipelines.agent_pipeline import execute_agent
from pipelines.agent_refinement import store_run_trace
from services.memory import (
    cleanup_expired_memories,
    format_memory_context,
    hydrate_agent_context,
    save_checkpoint,
    store_memory,
)

from .skills import _hydrate_skills

logger = logging.getLogger(__name__)


async def run_agent(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    input_data: dict = {},
) -> dict:
    """Trigger agent execution with memory hydration and persistence."""
    # Verify agent exists
    agent_stmt = select(Agent).where(
        Agent.id == uuid.UUID(agent_id),
        Agent.project_id == uuid.UUID(project_id),
    )
    agent_result = await db.execute(agent_stmt)
    agent = agent_result.scalar_one_or_none()
    if not agent:
        return {"error": "Agent not found"}

    # Cleanup expired working memories
    await cleanup_expired_memories(db, agent_id, project_id)

    # Hydrate agent memory context
    memory_context = await hydrate_agent_context(db, agent_id, project_id)
    memory_str = format_memory_context(memory_context)

    # Inject memory into input_data if there's anything to inject
    enriched_input = dict(input_data)
    if memory_str:
        enriched_input["_memory_context"] = memory_str

    # Hydrate skills into prompt
    skills_text = await _hydrate_skills(db, agent_id)
    if skills_text:
        enriched_input["_skills_context"] = skills_text

    # Create task record
    task = AgentTask(
        id=uuid.uuid4(),
        agent_id=agent.id,
        input=input_data,
        status="running",
        trace=[],
        started_at=datetime.now(timezone.utc),
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
            input_data=enriched_input,
            db_session=db,
            project_id=project_id,
        ):
            trace.append(event)
            if event.get("status") == "completed" and event.get("step") == "post_process":
                final_output = event.get("output")
            elif event.get("status") == "error":
                task.status = "failed"
                task.error = event.get("error", "Unknown error")
                await save_checkpoint(
                    db, agent_id, str(task.id),
                    state={"last_input": input_data, "error": task.error, "trace_step": len(trace)},
                )
                break
        else:
            task.status = "completed"
            task.output = final_output

            # Save episodic memory: what the agent did and produced
            if final_output:
                await store_memory(
                    db, agent_id, project_id,
                    memory_type="episodic",
                    content={
                        "task_id": str(task.id),
                        "input_summary": json.dumps(input_data, default=str)[:500],
                        "output_summary": json.dumps(final_output, default=str)[:500],
                        "agent_type": agent.type,
                    },
                )

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        trace.append({
            "step": "execution",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await save_checkpoint(
            db, agent_id, str(task.id),
            state={"last_input": input_data, "error": str(e), "trace_step": len(trace)},
        )

    task.trace = trace
    task.completed_at = datetime.now(timezone.utc)

    # Store run trace for refinement
    try:
        output_text = json.dumps(final_output, default=str) if final_output else ""
        tool_calls = []
        for t in trace:
            if t.get("step") == "tool_execution":
                tool_calls.append({
                    "tool": t.get("tool"),
                    "arguments": t.get("arguments"),
                    "result_preview": t.get("result_preview"),
                })

        skill_count_stmt = select(AgentSkill.id).where(AgentSkill.agent_id == agent.id)
        skill_result = await db.execute(skill_count_stmt)
        skills_used = [str(s.id) for s in skill_result.scalars().all()]

        measured_score = 1.0 if task.status == "completed" else 0.0
        measured_details = {}
        for t in trace:
            if t.get("step") == "evaluate":
                measured_score = t.get("score", measured_score)
                measured_details = t.get("details", {})
                break

        await store_run_trace(
            db=db,
            agent_id=agent_id,
            task_id=str(task.id),
            input_text=json.dumps(input_data, default=str)[:5000],
            output_text=output_text[:5000],
            tool_calls=tool_calls,
            scores={"score": measured_score, **measured_details},
            skills_used=skills_used,
        )
    except Exception as e:
        logger.warning(f"Failed to store run trace: {e}")

    # Update agent's last_active_at
    agent.last_active_at = datetime.now(timezone.utc)

    await db.flush()

    return {
        "task_id": str(task.id),
        "agent_id": str(agent.id),
        "status": task.status,
        "output": task.output,
        "error": task.error,
    }
