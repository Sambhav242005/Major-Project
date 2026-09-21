from datetime import timezone
from db.model_defs.base import Base, Column, DateTime, ForeignKey, JSON, String, Text, Uuid, datetime, gen_uuid, relationship


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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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


__all__ = ["Agent", "AgentTask"]
