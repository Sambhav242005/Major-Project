from db.model_defs.base import Base, Column, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, Uuid, datetime, gen_uuid, relationship


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


__all__ = ["Entity", "EntityMention", "Relationship"]
