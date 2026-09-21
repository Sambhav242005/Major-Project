"""Search tools — web search and knowledge base search."""

import json
import logging

from pipelines.embeddings import query_chunks
from pipelines.tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    name="web_search",
    description="Search the internet for current information. Returns web results with titles, URLs, and snippets.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Number of results (default 5)"},
        },
        "required": ["query"],
    },
)
async def web_search_tool(query: str, max_results: int = 5, **kwargs) -> str:
    """Search the web using DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return json.dumps({"results": [], "message": "No web results found."})
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append({
                "index": i,
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:500],
            })
        return json.dumps({"results": formatted})
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return json.dumps({"error": f"Web search failed: {e}"})


@register_tool(
    name="search_chunks",
    description="Search the knowledge base for relevant text chunks. Returns top results with source information.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "top_k": {"type": "integer", "description": "Number of results (default 5)"},
        },
        "required": ["query"],
    },
)
async def search_chunks_tool(query: str, top_k: int = 5, project_id: str = "", db=None, **kwargs) -> str:
    """Search ChromaDB for relevant chunks."""
    results = await query_chunks(query=query, project_id=project_id, top_k=top_k, db_session=db)
    if not results:
        return json.dumps({"results": [], "message": "No relevant chunks found."})

    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append({
            "index": i,
            "text": r["text"][:500],
            "filename": r.get("filename", "unknown"),
            "page_number": r.get("page_number", 0),
            "score": round(r.get("score", 0), 3),
        })
    return json.dumps({"results": formatted})
