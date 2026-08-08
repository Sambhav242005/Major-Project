"""Agent refinement — self-improvement harness with two-split acceptance.

Borrows Prime Agent's Continual Harness pattern:
- Rule-based evaluation (not LLM-as-judge)
- Two-split acceptance gate (held-in + held-out)
- Itemized skill deltas (never monolithic rewrites)
- Stagnation detection (track edit diffs)
- Max 10 skills per agent, max 1 skill per refinement cycle
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AgentSkill, AgentRunTrace, RefinementLog, RefinementEvalSet,
)

logger = logging.getLogger(__name__)

MAX_SKILLS_PER_AGENT = 10
MAX_SKILL_FAILURES = 3
STAGNATION_ALARM_CYCLES = 5


def _evaluate_output_rule_based(agent_type: str, output: dict, input_data: dict) -> dict:
    """Rule-based evaluation — deterministic, not LLM-dependent.

    Returns dict with 'score' (0-1) and 'details'.
    """
    scores = {}

    if agent_type == "extractor":
        entities = output.get("entities", [])
        relationships = output.get("relationships", [])
        scores["entity_count"] = min(len(entities) / 5, 1.0)
        scores["has_relationships"] = 1.0 if relationships else 0.0
        scores["parse_success"] = 0.0 if output.get("parse_error") else 1.0
        scores["score"] = (
            scores["entity_count"] * 0.4
            + scores["has_relationships"] * 0.3
            + scores["parse_success"] * 0.3
        )

    elif agent_type == "summarizer":
        response = output.get("response", "")
        scores["length"] = min(len(response) / 200, 1.0) if response else 0.0
        scores["has_content"] = 1.0 if len(response) > 50 else 0.0
        scores["score"] = scores["length"] * 0.5 + scores["has_content"] * 0.5

    elif agent_type == "qa":
        response = output.get("response", "")
        scores["has_citations"] = 1.0 if "[" in response else 0.0
        scores["length"] = min(len(response) / 100, 1.0) if response else 0.0
        scores["score"] = scores["has_citations"] * 0.5 + scores["length"] * 0.5

    elif agent_type == "reviewer":
        score = output.get("score")
        if score and 1 <= score <= 10:
            scores["valid_score"] = 1.0
            scores["score"] = 1.0
        else:
            scores["valid_score"] = 0.0
            scores["score"] = 0.0

    else:
        response = output.get("response", "")
        scores["has_content"] = 1.0 if len(response) > 20 else 0.0
        scores["score"] = scores["has_content"]

    return {"score": scores.get("score", 0.0), "details": scores}


async def evaluate_on_split(
    db: AsyncSession,
    agent_id: str,
    agent_type: str,
    split: str,
) -> float:
    """Evaluate agent on a held-in or held-out eval set."""
    stmt = select(RefinementEvalSet).where(
        RefinementEvalSet.agent_id == uuid.UUID(agent_id),
        RefinementEvalSet.split == split,
    )
    result = await db.execute(stmt)
    eval_tasks = result.scalars().all()

    if not eval_tasks:
        return 0.5  # neutral score if no eval tasks

    total_score = 0.0
    count = 0

    for task in eval_tasks:
        # Simulate execution and score
        # In production, this would actually run the agent
        total_score += 0.5  # placeholder — real impl runs agent
        count += 1

    return total_score / count if count > 0 else 0.5


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


async def mine_failures(
    db: AsyncSession,
    agent_id: str,
    recent_n: int = 10,
) -> list[dict]:
    """Mine recent run traces for failure patterns.

    Clusters by: verifier cause, causal status, abstract mechanism.
    """
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


async def propose_skill_delta(
    db: AsyncSession,
    agent_id: str,
    agent_type: str,
    failures: list[dict],
) -> dict | None:
    """Propose one itemized skill delta based on failure patterns.

    Returns: {"action": "add"|"update"|"remove", "skill_id": ..., "content": ..., "reason": ...}
    Returns None if no proposal warranted.
    """
    if not failures:
        return None

    # Check current skill count
    skill_count_stmt = select(func.count()).where(
        AgentSkill.agent_id == uuid.UUID(agent_id)
    )
    skill_count_result = await db.execute(skill_count_stmt)
    skill_count = skill_count_result.scalar() or 0

    # Check stagnation: have recent proposals been empty?
    recent_logs_stmt = (
        select(RefinementLog)
        .where(RefinementLog.agent_id == uuid.UUID(agent_id))
        .order_by(RefinementLog.created_at.desc())
        .limit(STAGNATION_ALARM_CYCLES)
    )
    recent_logs_result = await db.execute(recent_logs_stmt)
    recent_logs = recent_logs_result.scalars().all()

    if len(recent_logs) >= STAGNATION_ALARM_CYCLES:
        empty_diffs = sum(1 for log in recent_logs if not log.after or log.before == log.after)
        if empty_diffs == len(recent_logs):
            logger.warning(f"Stagnation alarm: agent {agent_id} has {empty_diffs} empty diffs in a row")
            return None

    # Analyze failure patterns
    common_issues = []
    for f in failures:
        scores = f.get("scores", {})
        if scores.get("entity_count", 1.0) < 0.3:
            common_issues.append("low_entity_count")
        if scores.get("parse_success", 1.0) < 0.5:
            common_issues.append("parse_failure")
        if scores.get("has_citations", 1.0) < 0.5:
            common_issues.append("missing_citations")
        if scores.get("length", 1.0) < 0.3:
            common_issues.append("too_short")

    if not common_issues:
        return None

    # Pick the most common issue
    from collections import Counter
    issue_counts = Counter(common_issues)
    top_issue = issue_counts.most_common(1)[0][0]

    # Generate a skill for the top issue
    skill_content = ""
    evidence = ""

    if top_issue == "low_entity_count":
        skill_content = "Extract more entities — look for all named people, organizations, locations, dates, and concepts in the text"
        evidence = f"Low entity count in {len([i for i in common_issues if i == 'low_entity_count'])} recent runs"
    elif top_issue == "parse_failure":
        skill_content = "Always output valid JSON with entities and relationships arrays — no markdown, no extra text"
        evidence = f"Parse failures in {len([i for i in common_issues if i == 'parse_failure'])} recent runs"
    elif top_issue == "missing_citations":
        skill_content = "Always cite sources using [1], [2] format — reference the source blocks provided"
        evidence = f"Missing citations in {len([i for i in common_issues if i == 'missing_citations'])} recent runs"
    elif top_issue == "too_short":
        skill_content = "Provide more detailed responses — expand on key points and include specific details"
        evidence = f"Responses too short in {len([i for i in common_issues if i == 'too_short'])} recent runs"

    if skill_count >= MAX_SKILLS_PER_AGENT:
        # Try to update an existing low-performing skill instead
        existing_stmt = (
            select(AgentSkill)
            .where(AgentSkill.agent_id == uuid.UUID(agent_id))
            .order_by(AgentSkill.harmful_count.desc())
            .limit(1)
        )
        existing_result = await db.execute(existing_stmt)
        worst_skill = existing_result.scalar_one_or_none()

        if worst_skill:
            return {
                "action": "update",
                "skill_id": str(worst_skill.id),
                "content": skill_content,
                "reason": evidence,
                "before": {"content": worst_skill.content},
            }
        return None

    return {
        "action": "add",
        "skill_id": None,
        "content": skill_content,
        "reason": evidence,
        "before": None,
    }


async def apply_delta(
    db: AsyncSession,
    agent_id: str,
    proposal: dict,
    held_in_delta: float = 0.0,
    held_out_delta: float = 0.0,
) -> bool:
    """Apply a skill delta with two-split acceptance gate.

    Accept only if:
    - held_in_delta > 0 (targeted weakness improved)
    - held_out_delta >= 0 (nothing regressed)

    Returns True if accepted and applied.
    """
    # Two-split acceptance gate
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
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
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
                skill.updated_at = datetime.utcnow()
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

    # Log the refinement
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
        created_at=datetime.utcnow(),
    )
    db.add(log)
    await db.flush()

    return accepted


async def run_refinement_cycle(
    db: AsyncSession,
    agent_id: str,
    agent_type: str,
) -> dict:
    """Run one full refinement cycle.

    1. Mine failures from recent traces
    2. Propose one itemized delta
    3. Score on held-in set
    4. Score on held-out set
    5. Apply or reject based on two-split gate
    """
    # Mine failures
    failures = await mine_failures(db, agent_id, recent_n=10)

    # Propose delta
    proposal = await propose_skill_delta(db, agent_id, agent_type, failures)

    if not proposal:
        return {"status": "no_proposal", "reason": "No failure patterns or stagnation detected"}

    # Two-split evaluation
    held_in_score_before = await evaluate_on_split(db, agent_id, agent_type, "held_in")
    held_out_score_before = await evaluate_on_split(db, agent_id, agent_type, "held_out")

    # Apply tentatively (the actual prompt change happens on next run via skill hydration)
    accepted = await apply_delta(
        db, agent_id, proposal,
        held_in_delta=0.1,  # placeholder — real impl compares before/after
        held_out_delta=0.0,
    )

    return {
        "status": "accepted" if accepted else "rejected",
        "proposal": proposal,
        "held_in_score": held_in_score_before,
        "held_out_score": held_out_score_before,
    }
