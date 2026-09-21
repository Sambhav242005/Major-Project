from datetime import timezone
from db.model_defs.base import Base, Column, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid, datetime, gen_uuid, relationship


class AgentMemory(Base):
    __tablename__ = "agent_memory"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Uuid(), ForeignKey("projects.id"), nullable=False)
    memory_type = Column(String(20), nullable=False)
    content = Column(JSON, nullable=False)
    embedding = Column(Text)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True))

    agent = relationship("Agent", back_populates="memories")


class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoints"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Uuid(), ForeignKey("agent_tasks.id"))
    state = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="checkpoints")


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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="skills")


__all__ = ["AgentCheckpoint", "AgentMemory", "AgentSkill"]
