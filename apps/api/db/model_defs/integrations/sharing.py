from datetime import timezone
from db.model_defs.base import Base, Column, DateTime, ForeignKey, String, UniqueConstraint, Uuid, datetime, gen_uuid, relationship


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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    source_project = relationship("Project", foreign_keys=[source_project_id])
    target_project = relationship("Project", foreign_keys=[target_project_id])


__all__ = ["ProjectMemoryShare"]
