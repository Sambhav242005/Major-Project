from db.model_defs.base import Base, Column, DateTime, ForeignKey, JSON, Text, Uuid, datetime, gen_uuid


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


__all__ = ["AuditLog"]
