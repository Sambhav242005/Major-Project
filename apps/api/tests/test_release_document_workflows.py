"""Release regressions: originals, file-free retry, and evidence deletion."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from starlette.requests import Request
from starlette.responses import Response

from core.config import settings
from core.security import User
from db.models import Document, DocumentChunk, Entity, EntityMention, Project, Relationship
from db.session import Base
from services.documents.storage import save_original, load_original, original_path


def test_originals_are_durable_and_uuid_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    project, document = str(uuid.uuid4()), str(uuid.uuid4())
    save_original(project, document, b"source evidence")
    assert load_original(project, document) == b"source evidence"
    save_original(project, document, b"replacement")
    assert load_original(project, document) == b"replacement"
    assert original_path(project, document).is_relative_to(tmp_path)
    with pytest.raises(ValueError):
        original_path("../../outside", document)


@pytest.mark.asyncio
async def test_retry_uses_original_and_checks_project_first(tmp_path, monkeypatch):
    from routers.documents import router as documents_router
    import importlib
    routes = importlib.import_module("routers.documents.router")
    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    project, document = str(uuid.uuid4()), str(uuid.uuid4())
    save_original(project, document, b"durable original")
    status = AsyncMock(return_value={"status": "failed"})
    monkeypatch.setattr(routes.doc_service, "get_document_status", status)
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    row = Document(id=uuid.UUID(document), file_type="text/plain", status="failed")
    db = MagicMock(get=AsyncMock(return_value=row), commit=AsyncMock())
    request = Request({"type": "http", "method": "POST", "headers": []})
    result = await routes.retry_document(document, request, Response(), project, User(id=str(uuid.uuid4()), email="a@example.com"), db)
    assert result["status"] == "pending"
    assert row.status == "pending"
    assert started.call_args.args[2] == b"durable original"
    status.return_value = None
    with pytest.raises(Exception) as exc:
        await routes.retry_document(document, request, Response(), str(uuid.uuid4()), User(id=str(uuid.uuid4()), email="a@example.com"), db)
    assert getattr(exc.value, "status_code", None) == 404
    assert started.call_count == 1


@pytest.mark.asyncio
async def test_delete_removes_vectors_chunks_and_graph_evidence(monkeypatch):
    from services.documents.crud import delete_document
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    project, document, chunk, entity = (uuid.uuid4() for _ in range(4))
    deleted_vectors = []
    monkeypatch.setattr("pipelines.embeddings.delete_document_chunks", deleted_vectors.append)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("PRAGMA foreign_keys=ON"))
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            db.add(Project(id=project, name="Test"))
            await db.flush()
            db.add(Document(id=document, project_id=project, filename="test.txt", file_type="text/plain", storage_path="test", status="processed"))
            await db.flush()
            db.add_all([DocumentChunk(id=chunk, document_id=document, chunk_index=0, text="evidence", chroma_id="v0"), Entity(id=entity, project_id=project, name="Item", type="concept", first_seen_document_id=document)])
            await db.flush()
            db.add_all([EntityMention(entity_id=entity, document_id=document, chunk_id=chunk), Relationship(project_id=project, source_entity_id=entity, target_entity_id=entity, relation_type="related", source_document_id=document)])
            await db.commit()
            assert not await delete_document(db, str(document), str(uuid.uuid4()))
            assert deleted_vectors == []
            assert await delete_document(db, str(document), str(project))
            await db.commit()
            assert deleted_vectors == [str(document)]
            assert await db.get(Document, document) is None
            assert not (await db.execute(select(DocumentChunk))).scalars().all()
            assert not (await db.execute(select(EntityMention))).scalars().all()
            assert not (await db.execute(select(Relationship))).scalars().all()
    finally:
        await engine.dispose()
