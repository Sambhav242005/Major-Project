"""Background ingestion helpers and SSE subscribers for documents."""

import asyncio

from pipelines.ingestion import ingest_document, set_doc_notifier

# In-memory subscribers for document processing SSE
_doc_subscribers: dict[str, list[asyncio.Queue]] = {}

# Strong references to running ingestion tasks so the event loop never
# garbage-collects a task mid-run (same pattern as core.task_queue).
_running_ingestions: set[asyncio.Task] = set()


def _start_ingestion(session_factory, document_id: str, file_content: bytes) -> None:
    """Launch document ingestion in background. Non-blocking."""
    task = asyncio.create_task(ingest_document(session_factory, document_id, file_content))
    _running_ingestions.add(task)

    def _done(t: asyncio.Task):
        _running_ingestions.discard(t)

    task.add_done_callback(_done)


def _notify_doc_subscribers(document_id: str, event: dict):
    """Push event to all SSE subscribers watching this document."""
    if document_id in _doc_subscribers:
        dead = []
        for q in _doc_subscribers[document_id]:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _doc_subscribers[document_id].remove(q)


# Wire up the ingestion notifier
set_doc_notifier(_notify_doc_subscribers)
