"""Shim — re-exports from pipelines.tools for backward compatibility."""

from pipelines.tools import (
    TOOL_REGISTRY,
    execute_tool,
    get_document_chunks_tool,
    get_entity_tool,
    get_tool_schemas,
    register_tool,
    search_chunks_tool,
    store_entities_tool,
    web_search_tool,
)

__all__ = [
    "TOOL_REGISTRY",
    "register_tool",
    "execute_tool",
    "get_tool_schemas",
    "web_search_tool",
    "search_chunks_tool",
    "get_entity_tool",
    "get_document_chunks_tool",
    "store_entities_tool",
]
