"""Webhook dispatch — delivery attempts and retry scheduling."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WebhookDelivery, WebhookSubscription
from core.outbound import validate_public_https_url

from .signing import MAX_RETRIES, RETRY_DELAYS, _sign_payload

logger = logging.getLogger(__name__)
RETRY_BATCH_SIZE = 25
RETRY_POLL_SECONDS = 30
# SQLite has no row-level FOR UPDATE; serialize in-process dispatchers too.
_dispatch_lock = asyncio.Lock()


async def dispatch_delivery(db: AsyncSession, delivery_id: str) -> bool:
    """Dispatch a single webhook delivery via HTTP POST."""
    stmt = select(WebhookDelivery).where(
        WebhookDelivery.id == uuid.UUID(delivery_id)
    ).with_for_update(skip_locked=True)
    result = await db.execute(stmt)
    delivery = result.scalar_one_or_none()
    if not delivery or delivery.success or delivery.attempts >= MAX_RETRIES:
        return False
    if delivery.next_retry_at:
        due = delivery.next_retry_at.replace(tzinfo=timezone.utc) if delivery.next_retry_at.tzinfo is None else delivery.next_retry_at
        if due > datetime.now(timezone.utc):
            return False

    sub_stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == delivery.subscription_id
    )
    sub_result = await db.execute(sub_stmt)
    subscription = sub_result.scalar_one_or_none()
    if not subscription or not subscription.active:
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
        await validate_public_https_url(subscription.url)
        async with asyncio.timeout(15), httpx.AsyncClient(timeout=10.0, follow_redirects=False, trust_env=False) as client:
            async with client.stream("POST", subscription.url, content=payload_str, headers=headers) as resp:
                delivery.response_status = resp.status_code
                response_body = bytearray()
                async for chunk in resp.aiter_bytes(chunk_size=2000):
                    response_body.extend(chunk[:2000 - len(response_body)])
                    if len(response_body) >= 2000:
                        break
                delivery.response_body = response_body.decode("utf-8", errors="replace")
            delivery.attempts += 1

            if 200 <= resp.status_code < 300:
                delivery.success = True
                delivery.next_retry_at = None
                await db.flush()
                return True
            else:
                delivery.success = False
                if delivery.attempts < MAX_RETRIES:
                    delay = RETRY_DELAYS[min(delivery.attempts - 1, len(RETRY_DELAYS) - 1)]
                    delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                else:
                    delivery.next_retry_at = None
                await db.flush()
                return False

    except Exception as e:
        delivery.attempts += 1
        delivery.response_body = str(e)[:2000]
        delivery.response_status = None
        delivery.success = False
        if delivery.attempts < MAX_RETRIES:
            delay = RETRY_DELAYS[min(delivery.attempts - 1, len(RETRY_DELAYS) - 1)]
            delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        else:
            delivery.next_retry_at = None
        await db.flush()
        return False


async def dispatch_pending_deliveries(db: AsyncSession, project_id: str | None = None) -> int:
    async with _dispatch_lock:
        try:
            dispatched = await _dispatch_pending_deliveries(db, project_id)
            # Keep the SQLite process lock until writes become visible. Postgres
            # row locks remain held for the same complete transaction interval.
            await db.commit()
            return dispatched
        except BaseException:
            await db.rollback()
            raise


async def _dispatch_pending_deliveries(db: AsyncSession, project_id: str | None) -> int:
    """Dispatch all pending webhook deliveries that are due for retry."""
    stmt = select(WebhookDelivery).join(WebhookSubscription).where(
        WebhookSubscription.active == True,
        WebhookDelivery.success == False,
        WebhookDelivery.attempts < MAX_RETRIES,
        WebhookDelivery.next_retry_at <= datetime.now(timezone.utc),
    )
    if project_id is not None:
        stmt = stmt.where(WebhookSubscription.project_id == uuid.UUID(project_id))
    stmt = stmt.order_by(WebhookDelivery.next_retry_at, WebhookDelivery.id).limit(RETRY_BATCH_SIZE).with_for_update(skip_locked=True, of=WebhookDelivery)
    result = await db.execute(stmt)
    deliveries = result.scalars().all()

    dispatched = 0
    for delivery in deliveries:
        success = await dispatch_delivery(db, str(delivery.id))
        if success:
            dispatched += 1

    return dispatched


async def run_retry_scheduler(session_factory, *, poll_seconds=RETRY_POLL_SECONDS):
    """Run bounded batches in owned transactions; cancellation rolls back safely."""
    while True:
        try:
            async with session_factory() as db:
                try:
                    await dispatch_pending_deliveries(db)
                    await db.commit()
                except BaseException:
                    await db.rollback()
                    raise
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Webhook retry batch failed")
        await asyncio.sleep(poll_seconds)


async def stop_retry_scheduler(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
