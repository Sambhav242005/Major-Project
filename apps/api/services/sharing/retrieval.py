"""Sharing retrieval — cross-project memory access."""

from sqlalchemy.ext.asyncio import AsyncSession

from .permissions import get_shared_project_ids


async def retrieve_shared_memories(
    db: AsyncSession,
    agent_id: str,
    project_id: str,
    memory_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Retrieve memories from shared projects."""
    shared_project_ids = await get_shared_project_ids(db, project_id)
    if not shared_project_ids:
        return []

    from services.memory import retrieve_project_memories

    all_shared = []
    per_project_limit = max(1, limit // len(shared_project_ids))

    for shared_pid in shared_project_ids:
        memories = await retrieve_project_memories(
            db, shared_pid,
            memory_type=memory_type,
            limit=per_project_limit,
        )
        for m in memories:
            m["shared_from_project"] = shared_pid
        all_shared.extend(memories)

    all_shared.sort(key=lambda x: x["created_at"], reverse=True)
    return all_shared[:limit]
