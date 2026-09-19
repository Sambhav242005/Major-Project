"""Shared SSE streaming helpers.

Eliminates duplicated streaming patterns across agents, documents, and chat
routers. Both queue-based (task/document progress) and generator-based
(chat response) SSE streams use these helpers.
"""

import asyncio
import json
import logging
from typing import AsyncIterator, Callable, Awaitable

from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

# --- SSE formatting ---

def format_sse(event: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(event)}\n\n"


# --- Queue-based SSE (agents + documents) ---

KEEPALIVE_TIMEOUT = 30.0


async def queue_sse_stream(
    subscribe: Callable[[], asyncio.Queue],
    unsubscribe: Callable[[asyncio.Queue], None],
    *,
    done_condition: Callable[[dict], bool] = lambda e: e.get("step") == "complete",
    keepalive_timeout: float = KEEPALIVE_TIMEOUT,
) -> StreamingResponse:
    """Create an SSE response from an asyncio.Queue event source.

    Args:
        subscribe: Call to get a new asyncio.Queue subscribed to events.
        unsubscribe: Call to remove the queue when the stream ends.
        done_condition: Return True when the stream should close.
        keepalive_timeout: Seconds of inactivity before sending a keepalive.
    """
    async def _generate():
        q = subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=keepalive_timeout)
                except asyncio.TimeoutError:
                    yield format_sse({"step": "keepalive"})
                    continue

                yield format_sse(event)

                if done_condition(event):
                    break
        finally:
            unsubscribe(q)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Generator-based SSE (chat) ---

async def generator_sse_stream(
    generator: AsyncIterator[dict],
) -> StreamingResponse:
    """Create an SSE response from an async generator that yields dicts.

    The generator is expected to yield complete event dicts. Each dict
    is formatted as an SSE message and streamed to the client.
    """
    async def _generate():
        try:
            async for event in generator:
                yield format_sse(event)
        except Exception:
            logger.exception("SSE generator stream failed")
            yield format_sse({"step": "error", "status": "error", "error": "Stream interrupted"})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
