"""Webhook outbound — fire events to subscriptions."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WebhookDelivery, WebhookSubscription

from .signing import MAX_PAYLOAD_SIZE


async def fire_event(
    db: AsyncSession,
    project_id: str,
    event_type: str,
    payload: dict,
) -> int:
    """Fire a webhook event to all matching subscriptions."""
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.project_id == uuid.UUID(project_id),
        WebhookSubscription.event_type == event_type,
        WebhookSubscription.active == True,
    )
    result = await db.execute(stmt)
    subscriptions = result.scalars().all()

    if not subscriptions:
        return 0

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
            next_retry_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(delivery)
        deliveries_created += 1

    await db.flush()
    return deliveries_created
