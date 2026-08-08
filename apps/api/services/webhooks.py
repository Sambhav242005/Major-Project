"""Webhook service — outbound dispatch, retry, and inbound handling."""

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WebhookSubscription, WebhookDelivery, InboundWebhook

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [60, 300, 1800]  # 1min, 5min, 30min
MAX_PAYLOAD_SIZE = 65536  # 64KB


def _sign_payload(payload: str, secret: str) -> str:
    """Create HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def fire_event(
    db: AsyncSession,
    project_id: str,
    event_type: str,
    payload: dict,
) -> int:
    """Fire a webhook event to all matching subscriptions.

    Returns the number of deliveries created.
    """
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.project_id == uuid.UUID(project_id),
        WebhookSubscription.event_type == event_type,
        WebhookSubscription.active == True,
    )
    result = await db.execute(stmt)
    subscriptions = result.scalars().all()

    if not subscriptions:
        return 0

    # Truncate payload if too large
    payload_str = json.dumps(payload, default=str)
    if len(payload_str) > MAX_PAYLOAD_SIZE:
        payload = json.loads(payload_str[:MAX_PAYLOAD_SIZE])

    deliveries_created = 0

    for sub in subscriptions:
        delivery = WebhookDelivery(
            id=uuid.uuid4(),
            subscription_id=sub.id,
            event_type=event_type,
            payload=payload,
            attempts=0,
            success=False,
            next_retry_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.add(delivery)
        deliveries_created += 1

    await db.flush()
    return deliveries_created


async def dispatch_delivery(db: AsyncSession, delivery_id: str) -> bool:
    """Dispatch a single webhook delivery via HTTP POST."""
    stmt = select(WebhookDelivery).where(
        WebhookDelivery.id == uuid.UUID(delivery_id)
    )
    result = await db.execute(stmt)
    delivery = result.scalar_one_or_none()
    if not delivery:
        return False

    # Get subscription for URL and secret
    sub_stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == delivery.subscription_id
    )
    sub_result = await db.execute(sub_stmt)
    subscription = sub_result.scalar_one_or_none()
    if not subscription:
        return False

    payload_str = json.dumps(delivery.payload, default=str)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": delivery.event_type,
        "X-Webhook-Delivery": str(delivery.id),
    }

    if subscription.secret:
        signature = _sign_payload(payload_str, subscription.secret)
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                subscription.url,
                content=payload_str,
                headers=headers,
            )
            delivery.response_status = resp.status_code
            delivery.response_body = resp.text[:2000]
            delivery.attempts += 1

            if 200 <= resp.status_code < 300:
                delivery.success = True
                await db.flush()
                return True
            else:
                delivery.success = False
                if delivery.attempts < MAX_RETRIES:
                    delay = RETRY_DELAYS[min(delivery.attempts, len(RETRY_DELAYS) - 1)]
                    delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                await db.flush()
                return False

    except Exception as e:
        delivery.attempts += 1
        delivery.response_body = str(e)[:2000]
        delivery.success = False
        if delivery.attempts < MAX_RETRIES:
            delay = RETRY_DELAYS[min(delivery.attempts, len(RETRY_DELAYS) - 1)]
            delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
        await db.flush()
        return False


async def dispatch_pending_deliveries(db: AsyncSession) -> int:
    """Dispatch all pending webhook deliveries that are due for retry."""
    stmt = select(WebhookDelivery).where(
        WebhookDelivery.success == False,
        WebhookDelivery.attempts < MAX_RETRIES,
        WebhookDelivery.next_retry_at <= datetime.utcnow(),
    )
    result = await db.execute(stmt)
    deliveries = result.scalars().all()

    dispatched = 0
    for delivery in deliveries:
        success = await dispatch_delivery(db, str(delivery.id))
        if success:
            dispatched += 1

    return dispatched


def verify_inbound_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature for inbound webhook."""
    expected = _sign_payload(payload.decode("utf-8"), secret)
    return hmac.compare_digest(f"sha256={expected}", signature)


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
    from services.documents import create_document
    from pipelines.ingestion import ingest_document

    file_url = payload.get("file_url")
    filename = payload.get("filename", "webhook_upload")

    if not file_url:
        return {"error": "Missing file_url in payload"}

    # Download file
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(file_url)
            file_content = resp.content
    except Exception as e:
        return {"error": f"Failed to download file: {e}"}

    # Create document and trigger ingestion
    # This would need a user context — simplified for now
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
    from pipelines.chunking import chunk_pages
    from pipelines.embeddings import upsert_chunks
    from db.models import DocumentChunk, Document

    data = payload.get("data", "")
    source = payload.get("source", "mcp_receiver")

    if not data:
        return {"error": "No data in payload"}

    # Create a virtual document
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

    # Chunk the data
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
