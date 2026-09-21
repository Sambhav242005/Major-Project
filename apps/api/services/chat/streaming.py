"""Chat streaming — send_message orchestration with RAG retrieval."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security_utils import detect_injection, sanitize_for_llm
from db.models import ChatMessage
from pipelines.embeddings import query_chunks
from services.audit import write_audit_log

from .prompt import build_entity_context, build_messages, build_user_prompt
from .retrieval import _expand_via_graph, _format_source_block, _get_entity_context

logger = logging.getLogger(__name__)


async def send_message(
    db: AsyncSession,
    session_id: str,
    message: str,
    project_id: str,
    actor_id,
):
    """Stream assistant response with RAG retrieval.

    Async generator that yields SSE-formatted events:
    - {"type": "chunk", "content": "..."} — incremental text
    - {"type": "citations", "citations": [...]} — source citations
    - {"type": "done"} — stream complete
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

    # Step 1: Retrieve relevant chunks via ChromaDB
    search_results = await query_chunks(query=message, project_id=project_id, top_k=8, db_session=db)

    # Step 2: Enrich with entity context
    chunk_ids = [r.get("chunk_id", "") for r in search_results]
    entities = await _get_entity_context(db, project_id, chunk_ids)

    # Step 3: Graph expansion — get neighboring entities
    entity_ids = [e["id"] for e in entities]
    expanded = await _expand_via_graph(db, project_id, entity_ids, depth=1)

    # Step 4: Build source blocks
    source_blocks = []
    citations = []

    for i, r in enumerate(search_results, 1):
        block = _format_source_block(
            index=i,
            text=r["text"],
            filename=r.get("filename", "unknown"),
            page_number=r.get("page_number", 0),
            doc_id=r.get("document_id", ""),
        )
        source_blocks.append(block)
        citations.append({
            "index": i,
            "chunk_id": r.get("chunk_id", ""),
            "document_id": r.get("document_id", ""),
            "filename": r.get("filename", "unknown"),
            "page_number": r.get("page_number", 0),
        })

    # Step 5: Build entity context for prompt
    entity_context = build_entity_context(entities, expanded)

    # Step 6: Assemble prompt
    sources_text = "\n\n---\n\n".join(source_blocks) if source_blocks else "No relevant sources found."

    # Get chat history
    history_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == (uuid.UUID(session_id) if not isinstance(session_id, uuid.UUID) else session_id))
        .order_by(ChatMessage.created_at)
        .limit(20)
    )
    history_result = await db.execute(history_stmt)
    history = history_result.scalars().all()

    history_text = ""
    for msg in history[:-1]:  # Exclude the just-added user message
        if msg.role == "user":
            history_text += f"User: {msg.content}\n"
        elif msg.role == "assistant":
            history_text += f"Assistant: {msg.content[:200]}\n"

    user_prompt = build_user_prompt(sources_text, entity_context, history_text, message)
    messages = build_messages(user_prompt)

    # Step 7: Stream LLM response
    full_response = ""
    try:
        from pipelines.llm_client import chat_completion_stream

        async for chunk in chat_completion_stream(
            messages=messages,
            model=settings.LLM_CHAT_MODEL,
            temperature=0.3,
        ):
            full_response += chunk
            yield {"type": "chunk", "content": chunk}

    except Exception as e:
        logger.exception(f"Chat streaming failed: {e}")
        error_msg = "I encountered an error processing your question. Please try again."
        full_response = error_msg
        yield {"type": "chunk", "content": error_msg}

    # Step 8: Send citations
    yield {"type": "citations", "citations": citations}

    # Step 9: Save assistant message
    assistant_msg = ChatMessage(
        session_id=uuid.UUID(session_id) if not isinstance(session_id, uuid.UUID) else session_id,
        role="assistant",
        content=full_response,
        citations=citations,
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

    yield {"type": "done"}
