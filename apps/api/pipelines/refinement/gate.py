"""Acceptance gate and refinement cycle."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentSkill, RefinementLog
from pipelines.refinement.evaluation import evaluate_on_split
from pipelines.refinement.skills import propose_skill_delta
from pipelines.refinement.traces import mine_failures


async def apply_delta(
    db: AsyncSession,
    agent_id: str,
    proposal: dict,
    held_in_delta: float = 0.0,
    held_out_delta: float = 0.0,
) -> bool:
    """Apply a skill delta with two-split acceptance gate."""
    accepted = held_in_delta > 0 and held_out_delta >= 0

    if proposal["action"] == "add":
        if accepted:
            new_skill = AgentSkill(
                id=uuid.uuid4(),
                agent_id=uuid.UUID(agent_id),
                skill_type="prompt_hint",
                content=proposal["content"],
                evidence=proposal["reason"],
                success_count=0,
                failure_count=0,
                helpful_count=0,
                harmful_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(new_skill)
        target_id = None

    elif proposal["action"] == "update":
        if accepted and proposal.get("skill_id"):
            stmt = select(AgentSkill).where(
                AgentSkill.id == uuid.UUID(proposal["skill_id"])
            )
            result = await db.execute(stmt)
            skill = result.scalar_one_or_none()
            if skill:
                skill.content = proposal["content"]
                skill.evidence = proposal["reason"]
                skill.updated_at = datetime.now(timezone.utc)
        target_id = proposal.get("skill_id")

    elif proposal["action"] == "remove":
        if accepted and proposal.get("skill_id"):
            stmt = select(AgentSkill).where(
                AgentSkill.id == uuid.UUID(proposal["skill_id"])
            )
            result = await db.execute(stmt)
            skill = result.scalar_one_or_none()
            if skill:
                await db.delete(skill)
        target_id = proposal.get("skill_id")
    else:
        target_id = proposal.get("skill_id")

    log = RefinementLog(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(agent_id),
        task_id=None,
        action=proposal["action"],
        target_id=uuid.UUID(target_id) if target_id else None,
        reason=proposal["reason"],
        before=proposal.get("before"),
        after={"content": proposal["content"]} if accepted else None,
        held_in_delta=held_in_delta,
        held_out_delta=held_out_delta,
        accepted=accepted,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()

    return accepted


async def run_refinement_cycle(
    db: AsyncSession,
    agent_id: str,
    agent_type: str,
) -> dict:
    """Run one full refinement cycle."""
    failures = await mine_failures(db, agent_id, recent_n=10)
    proposal = await propose_skill_delta(db, agent_id, agent_type, failures)

    if not proposal:
        return {"status": "no_proposal", "reason": "No failure patterns or stagnation detected"}

    held_in_score = await evaluate_on_split(db, agent_id, agent_type, "held_in")
    held_out_score = await evaluate_on_split(db, agent_id, agent_type, "held_out")

    held_in_delta = max(held_in_score - 0.5, 0.0)
    held_out_delta = held_out_score - held_in_score

    accepted = await apply_delta(
        db, agent_id, proposal,
        held_in_delta=held_in_delta,
        held_out_delta=held_out_delta,
    )

    return {
        "status": "accepted" if accepted else "rejected",
        "proposal": proposal,
        "held_in_score": held_in_score,
        "held_out_score": held_out_score,
        "held_in_delta": held_in_delta,
        "held_out_delta": held_out_delta,
    }
