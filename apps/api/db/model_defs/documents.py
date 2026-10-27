from datetime import timezone
from db.model_defs.base import Base, Column, DateTime, ForeignKey, Integer, String, Text, Uuid, datetime, gen_uuid, relationship


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
    mutation_version = Column(Integer, nullable=False, default=0, server_default="0")
    page_count = Column(Integer)
    error_message = Column(Text)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True))

    project = relationship("Project", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentSource(Base):
    __tablename__ = "document_sources"
    __table_args__ = {"extend_existing": True}

    id = Column(Uuid(), primary_key=True, default=gen_uuid)
    document_id = Column(Uuid(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(32), nullable=False, default="github")

    # GitHub provenance (Phase 1: public repositories). Retained so citations
    # can name the pinned owner/repo@commit and Phase 2 re-sync can compare
    # content hashes instead of re-downloading everything.
    repo_owner = Column(String(255), nullable=False)
    repo_name = Column(String(255), nullable=False)
    commit_sha = Column(String(40), nullable=False)
    file_path = Column(Text, nullable=False)
    blob_sha = Column(String(40))
    content_sha256 = Column(String(64))
    line_start = Column(Integer)
    line_end = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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


__all__ = ["Document", "DocumentChunk", "DocumentSource"]
