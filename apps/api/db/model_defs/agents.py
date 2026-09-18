from db.model_defs.base import Base, Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid, datetime, gen_uuid, relationship


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
    memory_type = Column(String(20), nullable=False)
    content = Column(JSON, nullable=False)
    embedding = Column(Text)
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
    state = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

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
    skills_used = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

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


__all__ = [
    "Agent",
    "AgentCheckpoint",
    "AgentMemory",
    "AgentRunTrace",
    "AgentSkill",
    "AgentTask",
    "RefinementEvalSet",
    "RefinementLog",
]
