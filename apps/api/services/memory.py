"""Agent memory service — CRUD, search, and lifecycle for agent memory.

Memory types:
  - working: short-lived task context (auto-expires)
  - episodic: past task results and interactions (persists)
  - semantic: learned facts and patterns (persists, consolidated)

All queries are scoped by (project_id, agent_id) for multi-tenant isolation.
"""

import uuid
import json
import math
from datetime import datetime, timedelta

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentMemory, AgentCheckpoint


# --- Memory CRUD ---


async def store_memory(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    memory_type: str,
    content: dict,
    embedding: list[float] | None = None,
    metadata: dict | None = None,
    ttl_hours: int | None = None,
) -> dict:
    """Store a memory for an agent.

    Args:
        agent_id: Agent UUID
        project_id: Project UUID (isolation key)
        memory_type: 'working' | 'episodic' | 'semantic'
        content: Memory payload (arbitrary dict)
        embedding: Optional vector for similarity search
        metadata: Optional metadata tags
        ttl_hours: Hours until expiry (working memory default: 24h)
    """
    if memory_type not in ("working", "episodic", "semantic"):
        raise ValueError(f"Invalid memory_type: {memory_type}")

    now = datetime.utcnow()
    expires_at = None
    if memory_type == "working":
        expires_at = now + timedelta(hours=ttl_hours or 24)
    elif ttl_hours:
        expires_at = now + timedelta(hours=ttl_hours)

    memory = AgentMemory(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(agent_id),
        project_id=uuid.UUID(project_id),
        memory_type=memory_type,
        content=content,
        embedding=json.dumps(embedding) if embedding else None,
        metadata_=metadata or {},
        created_at=now,
        expires_at=expires_at,
    )
    db.add(memory)
    await db.flush()

    return {
        "id": str(memory.id),
        "memory_type": memory.memory_type,
        "content": memory.content,
        "created_at": memory.created_at.isoformat(),
        "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
    }


async def retrieve_memories(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    memory_type: str | None = None,
    limit: int = 20,
    include_expired: bool = False,
) -> list[dict]:
    """Retrieve memories for an agent, optionally filtered by type.

    Results are ordered by created_at desc (most recent first).
    Expired working memories are excluded by default.
    """
    conditions = [
        AgentMemory.agent_id == uuid.UUID(agent_id),
        AgentMemory.project_id == uuid.UUID(project_id),
    ]
    if memory_type:
        conditions.append(AgentMemory.memory_type == memory_type)
    if not include_expired:
        conditions.append(
            (AgentMemory.expires_at.is_(None)) | (AgentMemory.expires_at > datetime.utcnow())
        )

    stmt = (
        select(AgentMemory)
        .where(and_(*conditions))
        .order_by(AgentMemory.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    memories = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "content": m.content,
            "metadata": m.metadata_ or {},
            "created_at": m.created_at.isoformat(),
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        }
        for m in memories
    ]


async def search_memories(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    query_embedding: list[float],
    memory_type: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Find memories most similar to query_embedding via cosine similarity.

    Loads candidate memories into memory, computes cosine similarity,
    returns top-k. For production, use pgvector or a vector DB.
    """
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

    # Compute cosine similarity
    scored = []
    for m in memories:
        if not m.embedding:
            continue
        stored = json.loads(m.embedding)
        sim = _cosine_similarity(query_embedding, stored)
        scored.append((sim, m))

    # Sort by similarity desc, take top-k
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


async def delete_memory(db: AsyncSession, memory_id: str, agent_id: str, project_id: str) -> bool:
    """Delete a specific memory. Verifies ownership."""
    stmt = select(AgentMemory).where(
        AgentMemory.id == uuid.UUID(memory_id),
        AgentMemory.agent_id == uuid.UUID(agent_id),
        AgentMemory.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()
    if not memory:
        return False
    await db.delete(memory)
    await db.flush()
    return True


async def cleanup_expired_memories(db: AsyncSession, agent_id: str, project_id: str) -> int:
    """Delete expired working memories. Returns count deleted."""
    stmt = delete(AgentMemory).where(
        AgentMemory.agent_id == uuid.UUID(agent_id),
        AgentMemory.project_id == uuid.UUID(project_id),
        AgentMemory.memory_type == "working",
        AgentMemory.expires_at.isnot(None),
        AgentMemory.expires_at < datetime.utcnow(),
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount


async def retrieve_project_memories(
    db: AsyncSession,
    project_id: str,
    memory_type: str | None = None,
    limit: int = 20,
    include_expired: bool = False,
) -> list[dict]:
    """Retrieve memories for a project, regardless of agent.

    Used for cross-project sharing — memories belong to the project,
    not to a specific agent.
    """
    conditions = [
        AgentMemory.project_id == uuid.UUID(project_id),
    ]
    if memory_type:
        conditions.append(AgentMemory.memory_type == memory_type)
    if not include_expired:
        conditions.append(
            (AgentMemory.expires_at.is_(None)) | (AgentMemory.expires_at > datetime.utcnow())
        )

    stmt = (
        select(AgentMemory)
        .where(and_(*conditions))
        .order_by(AgentMemory.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    memories = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "content": m.content,
            "metadata": m.metadata_ or {},
            "created_at": m.created_at.isoformat(),
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        }
        for m in memories
    ]


# --- Checkpoints (for stop/resume) ---


async def save_checkpoint(
    db: AsyncSession,
    agent_id: str,
    task_id: str | None,
    state: dict,
) -> dict:
    """Save an agent checkpoint (working memory snapshot) for resume later."""
    checkpoint = AgentCheckpoint(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(agent_id),
        task_id=uuid.UUID(task_id) if task_id else None,
        state=state,
        created_at=datetime.utcnow(),
    )
    db.add(checkpoint)
    await db.flush()

    return {
        "id": str(checkpoint.id),
        "agent_id": str(checkpoint.agent_id),
        "state": checkpoint.state,
        "created_at": checkpoint.created_at.isoformat(),
    }


async def load_latest_checkpoint(
    db: AsyncSession,
    agent_id: str,
) -> dict | None:
    """Load the most recent checkpoint for an agent."""
    stmt = (
        select(AgentCheckpoint)
        .where(AgentCheckpoint.agent_id == uuid.UUID(agent_id))
        .order_by(AgentCheckpoint.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    checkpoint = result.scalar_one_or_none()
    if not checkpoint:
        return None

    return {
        "id": str(checkpoint.id),
        "agent_id": str(checkpoint.agent_id),
        "task_id": str(checkpoint.task_id) if checkpoint.task_id else None,
        "state": checkpoint.state,
        "created_at": checkpoint.created_at.isoformat(),
    }


# --- Memory hydration (load context into agent at startup) ---


async def hydrate_agent_context(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    max_working_memories: int = 10,
    max_episodic_memories: int = 5,
    max_semantic_memories: int = 10,
) -> dict:
    """Load an agent's memory context for injection into LLM prompts.

    Reads own project memories first, then shared memories from other projects.
    Returns a structured context dict ready to be formatted into a system message.
    """
    # Own memories
    working = await retrieve_memories(db, agent_id, project_id, "working", max_working_memories)
    episodic = await retrieve_memories(db, agent_id, project_id, "episodic", max_episodic_memories)
    semantic = await retrieve_memories(db, agent_id, project_id, "semantic", max_semantic_memories)

    # Shared memories from other projects
    from services.sharing import retrieve_shared_memories
    shared = await retrieve_shared_memories(db, agent_id, project_id, limit=10)

    # Also load latest checkpoint
    checkpoint = await load_latest_checkpoint(db, agent_id)

    return {
        "working_memory": [m["content"] for m in working],
        "episodic_memory": [m["content"] for m in episodic],
        "semantic_memory": [m["content"] for m in semantic],
        "shared_memory": [{"content": m["content"], "from_project": m.get("shared_from_project")} for m in shared],
        "checkpoint": checkpoint["state"] if checkpoint else None,
    }


def format_memory_context(context: dict) -> str:
    """Format hydrated memory context into a string for LLM system prompt."""
    parts = []

    if context.get("checkpoint"):
        parts.append(
            f"[RESUMED FROM CHECKPOINT]\n"
            f"Previous state: {json.dumps(context['checkpoint'], indent=2, default=str)}"
        )

    if context.get("working_memory"):
        items = "\n".join(
            f"- {json.dumps(m, default=str)}" for m in context["working_memory"][:5]
        )
        parts.append(f"[WORKING MEMORY]\n{items}")

    if context.get("episodic_memory"):
        items = "\n".join(
            f"- {json.dumps(m, default=str)}" for m in context["episodic_memory"][:3]
        )
        parts.append(f"[PAST EXPERIENCES]\n{items}")

    if context.get("semantic_memory"):
        items = "\n".join(
            f"- {json.dumps(m, default=str)}" for m in context["semantic_memory"][:5]
        )
        parts.append(f"[LEARNED FACTS]\n{items}")

    if context.get("shared_memory"):
        items = "\n".join(
            f"- [from project {m['from_project']}] {json.dumps(m['content'], default=str)}"
            for m in context["shared_memory"][:5]
        )
        parts.append(f"[SHARED MEMORIES FROM OTHER PROJECTS]\n{items}")

    if not parts:
        return ""

    return "\n\n".join(parts)


# --- Helpers ---


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
