"""Agent skills hydration — load learned skills into prompt context."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentSkill

MAX_SKILLS_PER_AGENT = 10


async def _hydrate_skills(db: AsyncSession, agent_id: str) -> str:
    """Load agent skills into prompt text."""
    stmt = (
        select(AgentSkill)
        .where(AgentSkill.agent_id == uuid.UUID(agent_id))
        .order_by(AgentSkill.helpful_count.desc())
        .limit(MAX_SKILLS_PER_AGENT)
    )
    result = await db.execute(stmt)
    skills = result.scalars().all()

    if not skills:
        return ""

    lines = ["Learned skills:"]
    for s in skills:
        counter = f"+{s.helpful_count}/-{s.harmful_count}" if s.helpful_count or s.harmful_count else "+0/-0"
        lines.append(f"- [{s.id}] \"{s.content}\" ({counter})")

    return "\n".join(lines)
