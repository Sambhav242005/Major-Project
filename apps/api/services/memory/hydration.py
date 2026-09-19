"""Memory hydration — load context for LLM prompt injection."""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from .checkpoints import load_latest_checkpoint
from .crud import retrieve_memories


async def hydrate_agent_context(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    max_working_memories: int = 10,
    max_episodic_memories: int = 5,
    max_semantic_memories: int = 10,
) -> dict:
    """Load an agent's memory context for injection into LLM prompts."""
    working = await retrieve_memories(db, agent_id, project_id, "working", max_working_memories)
    episodic = await retrieve_memories(db, agent_id, project_id, "episodic", max_episodic_memories)
    semantic = await retrieve_memories(db, agent_id, project_id, "semantic", max_semantic_memories)

    from services.sharing import retrieve_shared_memories
    shared = await retrieve_shared_memories(db, agent_id, project_id, limit=10)

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
