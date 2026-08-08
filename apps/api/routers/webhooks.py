"""Webhook routes — CRUD for subscriptions, inbound endpoint, delivery log."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db, get_project_id
from core.security import User, get_current_user
from db.models import WebhookSubscription, WebhookDelivery, InboundWebhook
from services.webhooks import (
    fire_event, dispatch_delivery, verify_inbound_signature,
    handle_inbound, dispatch_pending_deliveries,
)

router = APIRouter()


# --- Outbound Webhook Subscriptions ---

@router.get("/subscriptions")
async def list_subscriptions(
    project_id: str = Depends(get_project_id),
    db: AsyncSession = Depends(get_db),
):
    """List all webhook subscriptions for a project."""
    stmt = (
        select(WebhookSubscription)
        .where(WebhookSubscription.project_id == uuid.UUID(project_id))
        .order_by(WebhookSubscription.created_at.desc())
    )
    result = await db.execute(stmt)
    subs = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "event_type": s.event_type,
            "url": s.url,
            "active": s.active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in subs
    ]


@router.post("/subscriptions")
async def create_subscription(
    event_type: str,
    url: str,
    secret: str | None = None,
    project_id: str = Depends(get_project_id),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new webhook subscription."""
    sub = WebhookSubscription(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_id),
        event_type=event_type,
        url=url,
        secret=secret,
        active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(sub)
    await db.flush()

    return {
        "id": str(sub.id),
        "event_type": sub.event_type,
        "url": sub.url,
        "active": sub.active,
    }


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    project_id: str = Depends(get_project_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook subscription."""
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == uuid.UUID(subscription_id),
        WebhookSubscription.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    await db.delete(sub)
    await db.flush()
    return {"status": "deleted"}


@router.post("/test/{subscription_id}")
async def test_webhook(
    subscription_id: str,
    project_id: str = Depends(get_project_id),
    db: AsyncSession = Depends(get_db),
):
    """Fire a test event for a subscription."""
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == uuid.UUID(subscription_id),
        WebhookSubscription.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    count = await fire_event(
        db=db,
        project_id=project_id,
        event_type=sub.event_type,
        payload={"test": True, "message": "Test webhook delivery"},
    )

    return {"status": "test_fired", "deliveries_created": count}


# --- Delivery Log ---

@router.get("/deliveries")
async def list_deliveries(
    subscription_id: str | None = None,
    project_id: str = Depends(get_project_id),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """List webhook deliveries, optionally filtered by subscription."""
    stmt = (
        select(WebhookDelivery)
        .join(WebhookSubscription)
        .where(WebhookSubscription.project_id == uuid.UUID(project_id))
    )
    if subscription_id:
        stmt = stmt.where(WebhookDelivery.subscription_id == uuid.UUID(subscription_id))

    stmt = stmt.order_by(WebhookDelivery.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    deliveries = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "event_type": d.event_type,
            "success": d.success,
            "attempts": d.attempts,
            "response_status": d.response_status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in deliveries
    ]


# --- Inbound Webhook Endpoint ---

@router.post("/inbound/{slug}")
async def inbound_webhook(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive an inbound webhook POST."""
    body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": body.decode("utf-8", errors="replace")}

    headers = dict(request.headers)

    result = await handle_inbound(db=db, slug=slug, payload=payload, headers=headers)
    return result


# --- Retry pending ---

@router.post("/retry-pending")
async def retry_pending(
    db: AsyncSession = Depends(get_db),
):
    """Retry all pending webhook deliveries (admin endpoint)."""
    dispatched = await dispatch_pending_deliveries(db)
    return {"dispatched": dispatched}
