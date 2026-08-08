import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint, Uuid
)
from sqlalchemy.orm import relationship

from db.session import Base


def gen_uuid():
    return uuid.uuid4()


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    full_name = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    projects = relationship("Project", back_populates="owner")
    memberships = relationship("ProjectMember", back_populates="user")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=False)
    owner_id = Column(Uuid(), ForeignKey("profiles.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

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


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id"))
    uploaded_by = Column(Uuid(), ForeignKey("profiles.id"))
    filename = Column(Text, nullable=False)
    file_type = Column(Text, nullable=False)
    storage_path = Column(Text, nullable=False)
    status = Column(String(20), default="pending")
    page_count = Column(Integer)
    error_message = Column(Text)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True))

    project = relationship("Project", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    document_id = Column(Uuid(), ForeignKey("documents.id"))
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer)
    section_index = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    token_count = Column(Integer)
    chroma_id = Column(Text, nullable=False)

    document = relationship("Document", back_populates="chunks")


class Entity(Base):
    __tablename__ = "entities"

    __table_args__ = (UniqueConstraint("project_id", "name", "type"), {"extend_existing": True})

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id"))
    name = Column(Text, nullable=False)
    type = Column(String(20), nullable=False)
    description = Column(Text)
    first_seen_document_id = Column(Uuid(), ForeignKey("documents.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("project_id", "name", "type"),)

    project = relationship("Project", back_populates="entities")
    mentions = relationship("EntityMention", back_populates="entity")


class EntityMention(Base):
    __tablename__ = "entity_mentions"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    entity_id = Column(Uuid(), ForeignKey("entities.id"))
    document_id = Column(Uuid(), ForeignKey("documents.id"))
    chunk_id = Column(Uuid(), ForeignKey("document_chunks.id"))
    mention_text = Column(Text)
    confidence = Column(Float)

    entity = relationship("Entity", back_populates="mentions")


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id"))
    source_entity_id = Column(Uuid(), ForeignKey("entities.id"))
    target_entity_id = Column(Uuid(), ForeignKey("entities.id"))
    relation_type = Column(Text, nullable=False)
    description = Column(Text)
    confidence = Column(Float)
    source_document_id = Column(Uuid(), ForeignKey("documents.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    project = relationship("Project", back_populates="relationships")
    source_entity = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity = relationship("Entity", foreign_keys=[target_entity_id])


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id"))
    user_id = Column(Uuid(), ForeignKey("profiles.id"))
    title = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    project = relationship("Project", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    session_id = Column(Uuid(), ForeignKey("chat_sessions.id"))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    project_id = Column(Uuid(), ForeignKey("projects.id"))
    owner_id = Column(Uuid(), ForeignKey("profiles.id"))
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    config = Column(JSON, default=dict)
    status = Column(String(20), default="active")
    last_checkpoint = Column(JSON)
    last_active_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    project = relationship("Project", back_populates="agents")
    owner = relationship("Profile")
    tasks = relationship("AgentTask", back_populates="agent")
    memories = relationship("AgentMemory", back_populates="agent", cascade="all, delete-orphan")
    checkpoints = relationship("AgentCheckpoint", back_populates="agent", cascade="all, delete-orphan")
    skills = relationship("AgentSkill", back_populates="agent", cascade="all, delete-orphan")
    run_traces = relationship("AgentRunTrace", back_populates="agent", cascade="all, delete-orphan")


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id"))
    input = Column(JSON)
    output = Column(JSON)
    status = Column(String(20), default="queued")
    trace = Column(JSON)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error = Column(Text)

    agent = relationship("Agent", back_populates="tasks")


class AgentMemory(Base):
    __tablename__ = "agent_memory"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Uuid(), ForeignKey("projects.id"), nullable=False)
    memory_type = Column(String(20), nullable=False)  # working, episodic, semantic
    content = Column(JSON, nullable=False)
    embedding = Column(Text)  # JSON array of floats for vector similarity
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))

    agent = relationship("Agent", back_populates="memories")


class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoints"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Uuid(), ForeignKey("agent_tasks.id"))
    state = Column(JSON, nullable=False)  # working memory snapshot
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    agent = relationship("Agent", back_populates="checkpoints")


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


class ProjectMemoryShare(Base):
    """Cross-project memory sharing with permissions."""
    __tablename__ = "project_memory_shares"
    __table_args__ = (
        UniqueConstraint("source_project_id", "target_project_id"),
        {"extend_existing": True},
    )

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    source_project_id = Column(Uuid(), ForeignKey("projects.id"), nullable=False)
    target_project_id = Column(Uuid(), ForeignKey("projects.id"), nullable=False)
    permission = Column(String(10), nullable=False, default="read")  # read | read_write
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


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    skill_type = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    evidence = Column(Text)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    helpful_count = Column(Integer, default=0)
    harmful_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    agent = relationship("Agent", back_populates="skills")


class AgentRunTrace(Base):
    __tablename__ = "agent_run_traces"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Uuid(), ForeignKey("agent_tasks.id", ondelete="SET NULL"))
    input_text = Column(Text, nullable=False)
    output_text = Column(Text)
    tool_calls = Column(JSON)
    scores = Column(JSON)
    skills_used = Column(JSON)  # list of skill UUIDs
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    agent = relationship("Agent", back_populates="run_traces")


class RefinementEvalSet(Base):
    __tablename__ = "refinement_eval_sets"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    split = Column(Text, nullable=False)  # 'held_in' or 'held_out'
    task_name = Column(Text, nullable=False)
    input_text = Column(Text, nullable=False)
    expected_output = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class RefinementLog(Base):
    __tablename__ = "refinement_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Uuid(), ForeignKey("agent_tasks.id", ondelete="SET NULL"))
    action = Column(Text, nullable=False)
    target_id = Column(Uuid())
    reason = Column(Text, nullable=False)
    before = Column(JSON)
    after = Column(JSON)
    held_in_delta = Column(Float)
    held_out_delta = Column(Float)
    accepted = Column(Boolean, default=False)
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
