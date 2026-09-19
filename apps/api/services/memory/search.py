"""Memory search — cosine similarity over stored embeddings."""

import json
import math
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentMemory


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def search_memories(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    query_embedding: list[float],
    memory_type: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Find memories most similar to query_embedding via cosine similarity."""
    conditions = [
        AgentMemory.agent_id == uuid.UUID(agent_id),
        AgentMemory.project_id == uuid.UUID(project_id),
        AgentMemory.embedding.isnot(None),
    ]
    if memory_type:
        conditions.append(AgentMemory.memory_type == memory_type)

    stmt = select(AgentMemory).where(and_(*conditions))
    result = await db.execute(stmt)
    memories = result.scalars().all()

    scored = []
    for m in memories:
        if not m.embedding:
            continue
        stored = json.loads(m.embedding)
        sim = _cosine_similarity(query_embedding, stored)
        scored.append((sim, m))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "content": m.content,
            "metadata": m.metadata_ or {},
            "similarity": round(sim, 4),
            "created_at": m.created_at.isoformat(),
        }
        for sim, m in scored[:limit]
    ]
