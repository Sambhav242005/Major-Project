"""Webhook dispatch — delivery attempts and retry scheduling."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WebhookDelivery, WebhookSubscription

from .signing import MAX_RETRIES, RETRY_DELAYS, _sign_payload


async def dispatch_delivery(db: AsyncSession, delivery_id: str) -> bool:
    """Dispatch a single webhook delivery via HTTP POST."""
    stmt = select(WebhookDelivery).where(
        WebhookDelivery.id == uuid.UUID(delivery_id)
    )
    result = await db.execute(stmt)
    delivery = result.scalar_one_or_none()
    if not delivery:
        return False

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
                    delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                await db.flush()
                return False

    except Exception as e:
        delivery.attempts += 1
        delivery.response_body = str(e)[:2000]
        delivery.success = False
        if delivery.attempts < MAX_RETRIES:
            delay = RETRY_DELAYS[min(delivery.attempts, len(RETRY_DELAYS) - 1)]
            delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        await db.flush()
        return False


async def dispatch_pending_deliveries(db: AsyncSession) -> int:
    """Dispatch all pending webhook deliveries that are due for retry."""
    stmt = select(WebhookDelivery).where(
        WebhookDelivery.success == False,
        WebhookDelivery.attempts < MAX_RETRIES,
        WebhookDelivery.next_retry_at <= datetime.now(timezone.utc),
    )
    result = await db.execute(stmt)
    deliveries = result.scalars().all()

    dispatched = 0
    for delivery in deliveries:
        success = await dispatch_delivery(db, str(delivery.id))
        if success:
            dispatched += 1

    return dispatched
