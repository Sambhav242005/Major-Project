"""Webhook inbound — routing and handlers for inbound webhooks."""

import uuid
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import InboundWebhook


async def handle_inbound(
    db: AsyncSession,
    slug: str,
    payload: dict,
    headers: dict = {},
) -> dict:
    """Route an inbound webhook to its handler."""
    stmt = select(InboundWebhook).where(
        InboundWebhook.slug == slug,
        InboundWebhook.active == True,
    )
    result = await db.execute(stmt)
    webhook = result.scalar_one_or_none()

    if not webhook:
        return {"error": f"No active webhook found for slug: {slug}"}

    handler = webhook.handler
    config = webhook.config or {}

    if handler == "ingest_document":
        return await _handle_ingest_document(db, webhook, payload, config)
    elif handler == "trigger_agent":
        return await _handle_trigger_agent(db, webhook, payload, config)
    elif handler == "mcp_receive":
        return await _handle_mcp_receive(db, webhook, payload, config)
    else:
        return {"error": f"Unknown handler: {handler}"}


async def _handle_ingest_document(
    db: AsyncSession,
    webhook: InboundWebhook,
    payload: dict,
    config: dict,
) -> dict:
    """Handle inbound document ingestion."""
    file_url = payload.get("file_url")
    filename = payload.get("filename", "webhook_upload")

    if not file_url:
        return {"error": "Missing file_url in payload"}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(file_url)
            file_content = resp.content
    except Exception as e:
        return {"error": f"Failed to download file: {e}"}

    return {"status": "received", "filename": filename, "size": len(file_content)}


async def _handle_trigger_agent(
    db: AsyncSession,
    webhook: InboundWebhook,
    payload: dict,
    config: dict,
) -> dict:
    """Handle inbound agent trigger."""
    from services.agents import run_agent

    agent_id = payload.get("agent_id") or config.get("agent_id")
    input_data = payload.get("input", {})

    if not agent_id:
        return {"error": "Missing agent_id in payload or config"}

    result = await run_agent(
        db=db,
        agent_id=agent_id,
        project_id=str(webhook.project_id),
        input_data=input_data,
    )
    return result


async def _handle_mcp_receive(
    db: AsyncSession,
    webhook: InboundWebhook,
    payload: dict,
    config: dict,
) -> dict:
    """Handle MCP data reception — chunk and embed into knowledge base."""
    from db.models import Document, DocumentChunk
    from pipelines.chunking import chunk_pages
    from pipelines.embeddings import upsert_chunks

    data = payload.get("data", "")
    source = payload.get("source", "mcp_receiver")

    if not data:
        return {"error": "No data in payload"}

    doc = Document(
        id=uuid.uuid4(),
        project_id=webhook.project_id,
        filename=f"mcp_{source}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt",
        file_type="text/plain",
        storage_path=f"mcp://{source}",
        status="processing",
    )
    db.add(doc)
    await db.flush()

    pages = [{"text": data, "page_number": 1}]
    chunks = chunk_pages(pages, max_tokens=600, overlap_tokens=80)

    if chunks:
        chroma_ids = upsert_chunks(
            chunks=chunks,
            project_id=str(webhook.project_id),
            document_id=str(doc.id),
        )

        for i, chunk in enumerate(chunks):
            db_chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=chunk["chunk_index"],
                page_number=chunk.get("page_number"),
                text=chunk["text"],
                token_count=chunk["token_count"],
                chroma_id=chroma_ids[i] if i < len(chroma_ids) else f"{doc.id}_chunk_{i}",
            )
            db.add(db_chunk)

    doc.status = "processed"
    doc.processed_at = datetime.utcnow()
    await db.flush()

    return {"status": "ingested", "document_id": str(doc.id), "chunk_count": len(chunks)}
