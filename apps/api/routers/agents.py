"""Shim for backward compatibility — re-exports from routers.agents package."""

try:
    from routers.agents import router  # noqa: F401
    from routers.agents.schemas import (  # noqa: F401
        AgentCreateRequest,
        AgentUpdateRequest,
        AgentRunRequest,
        MemoryStoreRequest,
        CheckpointSaveRequest,
    )
except Exception:  # pragma: no cover
    pass

__all__ = [
    "router",
    "AgentCreateRequest",
    "AgentUpdateRequest",
    "AgentRunRequest",
    "MemoryStoreRequest",
    "CheckpointSaveRequest",
]
