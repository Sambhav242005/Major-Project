from datetime import timezone
from db.model_defs.base import Base, Column, DateTime, ForeignKey, JSON, String, Text, Uuid, datetime, gen_uuid, relationship


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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    connection = relationship("MCPConnection", back_populates="auth_tokens")


__all__ = ["MCPAuthToken", "MCPConnection"]
