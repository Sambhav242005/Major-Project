from datetime import timezone
from db.model_defs.base import Base, Column, DateTime, ForeignKey, String, Text, Uuid, datetime, gen_uuid, relationship


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    full_name = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    projects = relationship("Project", back_populates="owner")
    memberships = relationship("ProjectMember", back_populates="user")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    owner_id = Column(Uuid(), ForeignKey("profiles.id"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner = relationship("Profile", back_populates="projects")
    members = relationship("ProjectMember", back_populates="project")
    documents = relationship("Document", back_populates="project")
    entities = relationship("Entity", back_populates="project")
    relationships = relationship("Relationship", back_populates="project")
    chat_sessions = relationship("ChatSession", back_populates="project")
    agents = relationship("Agent", back_populates="project")
    mcp_connections = relationship("MCPConnection", back_populates="project")
    webhook_subscriptions = relationship("WebhookSubscription", back_populates="project")
    inbound_webhooks = relationship("InboundWebhook", back_populates="project")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = {"extend_existing": True}

    project_id = Column(Uuid(), ForeignKey("projects.id"), primary_key=True)
    user_id = Column(Uuid(), ForeignKey("profiles.id"), primary_key=True)
    role = Column(String(20), default="viewer")

    project = relationship("Project", back_populates="members")
    user = relationship("Profile", back_populates="memberships")


__all__ = ["Profile", "Project", "ProjectMember"]
