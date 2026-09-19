"""Trace storage and failure mining."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentRunTrace, AgentSkill


async def store_run_trace(
    db: AsyncSession,
    agent_id: str,
    task_id: str,
    input_text: str,
    output_text: str,
    tool_calls: list[dict],
    scores: dict,
    skills_used: list[str],
) -> None:
    """Store raw execution trace for failure mining."""
    trace = AgentRunTrace(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(agent_id),
        task_id=uuid.UUID(task_id) if task_id else None,
        input_text=input_text[:5000],
        output_text=output_text[:5000],
        tool_calls=tool_calls,
        scores=scores,
        skills_used=skills_used,
        created_at=datetime.utcnow(),
    )
    db.add(trace)
    await db.flush()

    if skills_used and scores:
        score = scores.get("score", 0.0)
        helpful = score >= 0.7
        harmful = score < 0.4

        if helpful or harmful:
            skills_stmt = select(AgentSkill).where(
                AgentSkill.id.in_([uuid.UUID(s) for s in skills_used if s])
            )
            skills_result = await db.execute(skills_stmt)
            for skill in skills_result.scalars().all():
                if helpful:
                    skill.helpful_count += 1
                    skill.success_count += 1
                elif harmful:
                    skill.harmful_count += 1
                    skill.failure_count += 1
                skill.updated_at = datetime.utcnow()


async def mine_failures(
    db: AsyncSession,
    agent_id: str,
    recent_n: int = 10,
) -> list[dict]:
    """Mine recent run traces for failure patterns."""
    stmt = (
        select(AgentRunTrace)
        .where(AgentRunTrace.agent_id == uuid.UUID(agent_id))
        .order_by(AgentRunTrace.created_at.desc())
        .limit(recent_n)
    )
    result = await db.execute(stmt)
    traces = result.scalars().all()

    failures = []
    for trace in traces:
        if trace.scores and trace.scores.get("score", 1.0) < 0.5:
            failures.append({
                "trace_id": str(trace.id),
                "input_preview": trace.input_text[:200],
                "output_preview": trace.output_text[:200] if trace.output_text else "",
                "scores": trace.scores,
                "tool_calls": trace.tool_calls or [],
                "skills_used": trace.skills_used or [],
                "created_at": trace.created_at.isoformat() if trace.created_at else None,
            })

    return failures
