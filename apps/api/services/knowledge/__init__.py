"""Knowledge package — re-exports for backwards compatibility."""

from .graph import get_entity, get_entity_chunks, get_graph
from .search import search

__all__ = ["search", "get_entity", "get_graph", "get_entity_chunks"]
