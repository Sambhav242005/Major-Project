"""Skill delta proposal."""

import logging
import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentSkill, RefinementLog
from pipelines.refinement.constants import MAX_SKILLS_PER_AGENT, STAGNATION_ALARM_CYCLES

logger = logging.getLogger(__name__)


async def propose_skill_delta(
    db: AsyncSession,
    agent_id: str,
    agent_type: str,
    failures: list[dict],
) -> dict | None:
    """Propose one itemized skill delta based on failure patterns."""
    if not failures:
        return None

    skill_count_stmt = select(func.count()).where(
        AgentSkill.agent_id == uuid.UUID(agent_id)
    )
    skill_count_result = await db.execute(skill_count_stmt)
    skill_count = skill_count_result.scalar() or 0

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

    issue_counts = Counter(common_issues)
    top_issue = issue_counts.most_common(1)[0][0]

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
