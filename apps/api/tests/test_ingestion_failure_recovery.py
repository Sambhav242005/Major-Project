"""A real failed database flush must produce a terminal document status."""
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import Document
from db.session import Base
from pipelines.ingestion import pipeline


@pytest.mark.asyncio
async def test_missing_chunk_column_rolls_back_and_records_failure(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    events = []
    monkeypatch.setattr(pipeline, "parse_document", lambda *_: [{"text": "A test document", "page_number": 1}])
    monkeypatch.setattr(pipeline, "chunk_pages", lambda *_: [{"text": "A test document", "page_number": 1, "chunk_index": 0, "token_count": 3}])
    monkeypatch.setattr(pipeline, "upsert_chunks", lambda *_: ["test_chunk_0"])
    monkeypatch.setattr("pipelines.embeddings.delete_document_chunks", lambda *_: None)
    monkeypatch.setattr(pipeline, "_notify", lambda _id, event: events.append(event))
    monkeypatch.setattr("services.webhooks.fire_event", AsyncMock())
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text("ALTER TABLE document_chunks DROP COLUMN section_index"))
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        identifier = uuid.uuid4()
        async with sessions() as db:
            db.add(Document(id=identifier, filename="test.txt", file_type="text/plain", storage_path="test.txt", status="pending"))
            await db.commit()
            await pipeline._ingest_document_body(db, str(identifier), b"A test document")
        async with sessions() as db:
            document = await db.get(Document, identifier)
            assert document.status == "failed"
            assert "section_index" in document.error_message
        assert events[-1]["status"] == "failed"
        assert events[-1]["stage"] == "failed"
    finally:
        await engine.dispose()
