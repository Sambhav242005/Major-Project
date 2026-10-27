"""Chat streaming — send_message orchestration with RAG retrieval."""

import logging
import uuid
from contextlib import aclosing
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security_utils import detect_injection, sanitize_for_llm
from db.models import ChatMessage
from pipelines.embeddings import query_chunks
from pipelines.llm_client import GenerationConfig
from pipelines.model_request_capture import ModelRequestCapture
from services.audit import write_audit_log

from .prompt import build_entity_context, build_messages, build_user_prompt
from .retrieval import (
    SOURCE_TEXT_TRUNCATE_CHARS,
    _expand_via_graph,
    _format_source_block,
    _get_entity_context,
)
from .request_capture import register_snapshot

logger = logging.getLogger(__name__)

# Prompt-window constants recorded in every snapshot ("included history").
HISTORY_WINDOW_LIMIT = 20
HISTORY_ASSISTANT_CLIP_CHARS = 200
RETRIEVAL_TOP_K = 8
ENTITY_CONTEXT_LIMIT = 10
EXPANDED_CONTEXT_LIMIT = 5


async def send_message(
    db: AsyncSession,
    session_id: str,
    message: str,
    project_id: str,
    actor_id,
    generation: GenerationConfig | None = None,
):
    """Stream assistant response with RAG retrieval.

    Async generator that yields SSE-formatted events:
    - {"type": "generation", "provider": "...", "model": "..."} — resolved generation for this answer
    - {"type": "chunk", "content": "..."} — incremental text
    - {"type": "citations", "citations": [...]} — source citations
    - {"type": "done", "request_id": "..."} — stream complete; request_id keys
      the read-only "Model request" snapshot (30-minute in-process retention)
    - {"type": "error", "error": "...", "request_id": "..."} — terminal
      failure; no completion follows
    """
    # Sanitize input
    message = sanitize_for_llm(message)

    if detect_injection(message):
        yield {"type": "error", "error": "Message rejected: potential prompt injection detected"}
        return

    # Save user message
    user_msg = ChatMessage(
        session_id=uuid.UUID(session_id) if not isinstance(session_id, uuid.UUID) else session_id,
        role="user",
        content=message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    await db.flush()

    # Announce the resolved generation before retrieval and streaming so the
    # client labels this answer even if the user switches models mid-stream.
    resolved_provider = (
        generation.requested_provider
        if generation and generation.requested_provider
        else ("configured" if generation is None else generation.provider)
    )
    resolved_model = generation.model if generation else settings.LLM_CHAT_MODEL
    resolved_generation = {
        "type": "generation",
        "provider": resolved_provider,
        "model": resolved_model,
    }
    yield resolved_generation

    # Step 1: Retrieve relevant chunks via ChromaDB
    search_results = await query_chunks(
        query=message, project_id=project_id, top_k=RETRIEVAL_TOP_K, db_session=db
    )

    # Step 2: Enrich with entity context
    chunk_ids = [r.get("chunk_id", "") for r in search_results]
    entities = await _get_entity_context(db, project_id, chunk_ids)

    # Step 3: Graph expansion — get neighboring entities
    entity_ids = [e["id"] for e in entities]
    expanded = await _expand_via_graph(db, project_id, entity_ids, depth=1)

    # Step 4: Build source blocks
    source_blocks = []
    citations = []
    snapshot_sources = []

    for i, r in enumerate(search_results, 1):
        block = _format_source_block(
            index=i,
            text=r["text"],
            filename=r.get("filename", "unknown"),
            page_number=r.get("page_number", 0),
            doc_id=r.get("document_id", ""),
            source_location=r.get("source_location"),
        )
        source_blocks.append(block)
        citations.append({
            "index": i,
            "chunk_id": r.get("chunk_id", ""),
            "document_id": r.get("document_id", ""),
            "filename": r.get("filename", "unknown"),
            "page_number": r.get("page_number", 0),
        })
        truncated = len(r["text"]) > SOURCE_TEXT_TRUNCATE_CHARS
        snapshot_sources.append({
            "index": i,
            "chunk_id": r.get("chunk_id", ""),
            "document_id": r.get("document_id", ""),
            "filename": r.get("filename", "unknown"),
            "page_number": r.get("page_number", 0),
            "text": r["text"][:SOURCE_TEXT_TRUNCATE_CHARS],
            "truncated": truncated,
            "original_characters": len(r["text"]),
        })
        if r.get("source_location"):
            citations[-1]["source_location"] = r["source_location"]
            snapshot_sources[-1]["source_location"] = r["source_location"]

    # Step 5: Build entity context for prompt
    entity_context = build_entity_context(entities, expanded)

    # Step 6: Assemble prompt
    sources_text = "\n\n---\n\n".join(source_blocks) if source_blocks else "No relevant sources found."

    # Get chat history
    history_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == (uuid.UUID(session_id) if not isinstance(session_id, uuid.UUID) else session_id))
        .order_by(ChatMessage.created_at)
        .limit(HISTORY_WINDOW_LIMIT)
    )
    history_result = await db.execute(history_stmt)
    history = history_result.scalars().all()

    history_text = ""
    history_entries = []
    for msg in history[:-1]:  # Exclude the just-added user message
        if msg.role == "user":
            history_text += f"User: {msg.content}\n"
            history_entries.append({
                "role": "user",
                "content": msg.content,
                "truncated": False,
            })
        elif msg.role == "assistant":
            history_text += f"Assistant: {msg.content[:HISTORY_ASSISTANT_CLIP_CHARS]}\n"
            history_entries.append({
                "role": "assistant",
                "content": msg.content[:HISTORY_ASSISTANT_CLIP_CHARS],
                "truncated": len(msg.content) > HISTORY_ASSISTANT_CLIP_CHARS,
            })

    user_prompt = build_user_prompt(sources_text, entity_context, history_text, message)
    messages = build_messages(user_prompt)

    # Sanitized snapshot of the outbound generation request, filled in by
    # pipelines.llm_client at the final application transport boundary.
    capture = ModelRequestCapture(
        request_id=str(uuid.uuid4()),
        assembly={
            "flow": "chat.send_message",
            "session_id": str(session_id),
            "user_message": {
                "role": "user",
                "content": message,
                "sanitization_applied": ["router sanitize_input", "service sanitize_for_llm"],
            },
            "history": {
                "window_limit": HISTORY_WINDOW_LIMIT,
                "rows_returned_by_window": len(history),
                "included_entries": len(history_entries),
                "assistant_clipped_to_chars": HISTORY_ASSISTANT_CLIP_CHARS,
                "may_exclude_older_messages": len(history) >= HISTORY_WINDOW_LIMIT,
                "entries": history_entries,
            },
            "retrieval": {
                "top_k": RETRIEVAL_TOP_K,
                "query": message,
                "source_count": len(search_results),
                "source_text_truncated_to_chars": SOURCE_TEXT_TRUNCATE_CHARS,
                "sources": snapshot_sources,
                "truncation_decisions": "per-source text clipped to "
                f"{SOURCE_TEXT_TRUNCATE_CHARS} characters before prompt assembly",
            },
            "graph_context": {
                "entities": entities,
                "entities_shown_in_prompt": min(ENTITY_CONTEXT_LIMIT, len(entities)),
                "entities_omitted": max(0, len(entities) - ENTITY_CONTEXT_LIMIT),
                "expanded": expanded,
                "expanded_shown_in_prompt": min(EXPANDED_CONTEXT_LIMIT, len(expanded)),
                "expanded_omitted": max(0, len(expanded) - EXPANDED_CONTEXT_LIMIT),
            },
            "attachments": [],
            "tools": {"present": False},
        },
    )
    request_id = capture.request_id
    registered = False

    def _register_capture() -> None:
        """Store the finished snapshot once, only after a terminal status."""
        nonlocal registered
        if registered or not capture.terminal:
            return
        snapshot = capture.snapshot()
        snapshot["project_id"] = project_id
        snapshot["session_id"] = str(session_id)
        register_snapshot(snapshot)
        registered = True

    # Step 7: Stream LLM response
    full_response = ""
    stream_completed = False
    try:
        from pipelines.llm_client import chat_completion_stream

        llm_kwargs: dict = {"capture": capture}
        if generation:
            llm_kwargs["generation"] = generation
        async with aclosing(chat_completion_stream(
            messages=messages,
            model=settings.LLM_CHAT_MODEL,
            temperature=0.3,
            **llm_kwargs,
        )) as provider_stream:
            async for chunk in provider_stream:
                full_response += chunk
                yield {"type": "chunk", "content": chunk}
        stream_completed = True
        _register_capture()

    except Exception:
        logger.exception("Chat streaming failed")
        # The response may already contain partial text. Tell the client to
        # discard it and never persist or announce it as a completed answer.
        if not capture.terminal:
            capture.mark_failed("generation failed before completion")
        _register_capture()
        await db.rollback()
        yield {"type": "error", "error": "The answer could not be completed. Please try again.", "request_id": request_id}
        return

    finally:
        if not stream_completed:
            # Client disconnect / cancellation / teardown before completion.
            if not capture.terminal:
                capture.mark_cancelled()
            _register_capture()

    # Step 8: Send citations
    yield {"type": "citations", "citations": citations}

    # Step 9: Save assistant message
    assistant_msg = ChatMessage(
        session_id=uuid.UUID(session_id) if not isinstance(session_id, uuid.UUID) else session_id,
        role="assistant",
        content=full_response,
        citations=citations,
        # Record only the resolved provider/model — never credentials.
        generation_provider=resolved_generation["provider"],
        generation_model=resolved_generation["model"],
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)
    await write_audit_log(
        db=db,
        project_id=project_id,
        actor_id=actor_id,
        action="chat.message_sent",
        resource_type="chat_session",
        resource_id=assistant_msg.session_id,
    )
    await db.commit()

    # Fire chat.completed webhook
    try:
        from services.webhooks import fire_event
        await fire_event(
            db=db,
            project_id=project_id,
            event_type="chat.completed",
            payload={
                "session_id": session_id,
                "message_id": str(assistant_msg.id),
                "citation_count": len(citations),
            },
        )
        await db.commit()
    except Exception:
        logger.warning("Failed to fire chat.completed webhook")

    yield {"type": "done", "request_id": request_id}
