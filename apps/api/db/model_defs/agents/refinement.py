from datetime import timezone
from db.model_defs.base import Base, Boolean, Column, DateTime, Float, ForeignKey, JSON, Text, Uuid, datetime, gen_uuid, relationship


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
    skills_used = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="run_traces")


class RefinementEvalSet(Base):
    __tablename__ = "refinement_eval_sets"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    agent_id = Column(Uuid(), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    split = Column(Text, nullable=False)
    task_name = Column(Text, nullable=False)
    input_text = Column(Text, nullable=False)
    expected_output = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


__all__ = ["AgentRunTrace", "RefinementEvalSet", "RefinementLog"]
