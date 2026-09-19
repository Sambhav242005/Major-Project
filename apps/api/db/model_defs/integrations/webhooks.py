from db.model_defs.base import Base, Boolean, Column, DateTime, ForeignKey, Integer, JSON, Text, Uuid, datetime, gen_uuid, relationship


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    secret = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    project = relationship("Project", back_populates="webhook_subscriptions")
    deliveries = relationship("WebhookDelivery", back_populates="subscription", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    subscription_id = Column(Uuid(), ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Text, nullable=False)
    payload = Column(JSON, nullable=False)
    response_status = Column(Integer)
    response_body = Column(Text)
    attempts = Column(Integer, default=0)
    success = Column(Boolean, default=False)
    next_retry_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    subscription = relationship("WebhookSubscription", back_populates="deliveries")


class InboundWebhook(Base):
    __tablename__ = "inbound_webhooks"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    handler = Column(Text, nullable=False)
    config = Column(JSON, default=dict)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    project = relationship("Project", back_populates="inbound_webhooks")


__all__ = ["InboundWebhook", "WebhookDelivery", "WebhookSubscription"]
