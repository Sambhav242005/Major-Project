"""Shim for backward compatibility — re-exports from routers.mcp package."""

try:
    from routers.mcp import router  # noqa: F401
    from routers.mcp.schemas import (  # noqa: F401
        MCPConnectionCreateRequest,
        MCPConnectionUpdateRequest,
        MCPSearchRequest,
    )
except Exception:  # pragma: no cover
    pass

__all__ = [
    "router",
    "MCPConnectionCreateRequest",
    "MCPConnectionUpdateRequest",
    "MCPSearchRequest",
]
