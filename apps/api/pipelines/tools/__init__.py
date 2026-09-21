"""Tools package — re-exports original agent_tools public API."""

from pipelines.tools.registry import TOOL_REGISTRY, execute_tool, get_tool_schemas, register_tool
from pipelines.tools.search_tools import search_chunks_tool, web_search_tool
from pipelines.tools.knowledge_tools import get_document_chunks_tool, get_entity_tool
from pipelines.tools.write_tools import store_entities_tool

# Ensure tool modules are imported so decorators register tools.
# Imports above already trigger registration via @register_tool.

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
