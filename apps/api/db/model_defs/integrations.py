from db.model_defs.base import Base, Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid, datetime, gen_uuid, relationship


class MCPConnection(Base):
    __tablename__ = "mcp_connections"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id"))
    direction = Column(String(10), nullable=False)
    name = Column(Text, nullable=False)
    endpoint_url = Column(Text)
    auth_config = Column(JSON)
    status = Column(String(20), default="disconnected")

    project = relationship("Project", back_populates="mcp_connections")
    auth_tokens = relationship("MCPAuthToken", back_populates="connection", cascade="all, delete-orphan")


class MCPAuthToken(Base):
    __tablename__ = "mcp_auth_tokens"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    connection_id = Column(Uuid(), ForeignKey("mcp_connections.id", ondelete="CASCADE"), nullable=False)
    access_token = Column(Text, nullable=False)
    token_type = Column(String(20), default="Bearer")
    refresh_token = Column(Text)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    scope = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    connection = relationship("MCPConnection", back_populates="auth_tokens")


class ProjectMemoryShare(Base):
    __tablename__ = "project_memory_shares"
    __table_args__ = (
        UniqueConstraint("source_project_id", "target_project_id"),
        {"extend_existing": True},
    )

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    source_project_id = Column(Uuid(), ForeignKey("projects.id"), nullable=False)
    target_project_id = Column(Uuid(), ForeignKey("projects.id"), nullable=False)
    permission = Column(String(10), nullable=False, default="read")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    source_project = relationship("Project", foreign_keys=[source_project_id])
    target_project = relationship("Project", foreign_keys=[target_project_id])


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id"))
    actor_id = Column(Uuid(), ForeignKey("profiles.id"))
    action = Column(Text, nullable=False)
    resource_type = Column(Text)
    resource_id = Column(Uuid())
    meta = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


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


__all__ = [
    "AuditLog",
    "InboundWebhook",
    "MCPAuthToken",
    "MCPConnection",
    "ProjectMemoryShare",
    "WebhookDelivery",
    "WebhookSubscription",
]
