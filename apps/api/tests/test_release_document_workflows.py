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
from core.errors import AppError, app_error_handler
from core.security import User
from db.models import Document, DocumentChunk, DocumentSource, Entity, EntityMention, Project, Relationship
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
    import importlib
    routes = importlib.import_module("routers.documents.router")
    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    project, document = str(uuid.uuid4()), str(uuid.uuid4())
    save_original(project, document, b"durable original")
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    row = Document(id=uuid.UUID(document), file_type="text/plain", status="failed")
    locked = AsyncMock(return_value=row)
    monkeypatch.setattr(routes.doc_service, "lock_document_for_mutation", locked)
    db = MagicMock(commit=AsyncMock())
    request = Request({"type": "http", "method": "POST", "headers": []})
    result = await routes.retry_document(document, request, Response(), project, User(id=str(uuid.uuid4()), email="a@example.com"), db)
    assert result["status"] == "pending"
    assert row.status == "pending"
    assert started.call_args.args[2] == b"durable original"
    locked.return_value = None
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
            db.add(DocumentSource(
                document_id=document, project_id=project, source_type="github",
                repo_owner="owner", repo_name="repo", commit_sha="a" * 40, file_path="test.txt",
            ))
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
            assert not (await db.execute(select(DocumentSource))).scalars().all()
    finally:
        await engine.dispose()


@pytest.fixture
def original_routes(tmp_path, monkeypatch):
    import importlib
    routes = importlib.import_module("routers.documents.router")
    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    return routes


@pytest.mark.parametrize("file_type,disposition,media_type", [
    ("application/pdf", "inline", "application/pdf"),
    ("text/markdown", "inline", "text/plain"),
    ("image/png", "inline", "image/png"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "attachment", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
])
def test_original_http_preview_keeps_sandbox(original_routes, monkeypatch, file_type, disposition, media_type):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core.security_headers import SecurityHeadersMiddleware
    routes = original_routes
    project, document = str(uuid.uuid4()), str(uuid.uuid4())
    save_original(project, document, b"original bytes")
    metadata = AsyncMock(return_value={"filename": '../résumé"\r\n.txt', "file_type": file_type})
    monkeypatch.setattr(routes.doc_service, "get_document", metadata)
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(routes.router, prefix="/documents")
    app.dependency_overrides[routes.get_project_id] = lambda: project
    app.dependency_overrides[routes.get_current_user] = lambda: MagicMock()
    app.dependency_overrides[routes.get_db] = lambda: MagicMock()
    with TestClient(app) as client:
        response = client.get(f"/documents/{document}/original?download=false")
        assert response.status_code == 200
        assert response.content == b"original bytes"
        header = response.headers["content-disposition"]
        assert header.startswith(disposition + "; filename*=utf-8''")
        assert "%0D%0A" in header and "\r" not in header and "%2F" not in header
        assert response.headers["content-type"].startswith(media_type)
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-security-policy"] == "sandbox; default-src 'none'"
        assert client.get(f"/documents/{document}/original").headers["content-disposition"].startswith("attachment;")
        metadata.return_value = None
        assert client.get(f"/documents/{document}/original").status_code == 404
        def not_a_member():
            raise HTTPException(status_code=403, detail="Not a member")
        app.dependency_overrides[routes.get_project_id] = not_a_member
        before = metadata.await_count
        assert client.get(f"/documents/{document}/original").status_code == 403
        assert metadata.await_count == before


@pytest.mark.asyncio
async def test_original_authorizes_before_storage(original_routes, monkeypatch):
    routes = original_routes
    monkeypatch.setattr(routes.doc_service, "get_document", AsyncMock(return_value=None))
    loaded = MagicMock(side_effect=AssertionError("unauthorized read"))
    monkeypatch.setattr(routes, "load_original", loaded)
    for identifier in [str(uuid.uuid4()), "../../secret"]:
        with pytest.raises(Exception) as exc:
            await routes.get_document_original(identifier, True, str(uuid.uuid4()), MagicMock(), MagicMock())
        assert exc.value.status_code == 404
    loaded.assert_not_called()


@pytest.mark.asyncio
async def test_missing_original_returns_404(original_routes, monkeypatch):
    routes = original_routes
    monkeypatch.setattr(routes.doc_service, "get_document", AsyncMock(return_value={"filename": "old.txt", "file_type": "text/plain"}))
    with pytest.raises(HTTPException) as exc:
        await routes.get_document_original(str(uuid.uuid4()), True, str(uuid.uuid4()), MagicMock(), MagicMock())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("rollback_fails", [False, True])
async def test_upload_commit_failure_cleans_original(original_routes, monkeypatch, rollback_fails):
    import inspect
    from io import BytesIO
    from starlette.datastructures import Headers, UploadFile
    routes = original_routes
    project, document = str(uuid.uuid4()), str(uuid.uuid4())
    uploaded = AsyncMock(return_value={"id": document, "filename": "source.txt"})
    monkeypatch.setattr(routes.doc_service, "upload_document", uploaded)
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    db = MagicMock(commit=AsyncMock(side_effect=RuntimeError("commit failed")), rollback=AsyncMock(side_effect=RuntimeError("rollback failed") if rollback_fails else None))
    file = UploadFile(BytesIO(b"source"), filename="source.txt", headers=Headers({"content-type": "text/plain"}))
    with pytest.raises(RuntimeError, match="commit failed"):
        await inspect.unwrap(routes.upload_document)(Request({"type": "http"}), Response(), file, project, MagicMock(), db)
    assert not original_path(project, document).exists()
    db.rollback.assert_awaited_once()
    started.assert_not_called()
    assert uploaded.call_args.kwargs["document_id"] in uploaded.call_args.kwargs["storage_path"]


@pytest.mark.asyncio
async def test_delete_commit_failure_restores_original(original_routes, monkeypatch):
    routes = original_routes
    project, document = str(uuid.uuid4()), str(uuid.uuid4())
    save_original(project, document, b"source")
    monkeypatch.setattr(routes.doc_service, "lock_document_for_mutation", AsyncMock(return_value=Document(status="failed")))
    monkeypatch.setattr(routes.doc_service, "delete_document", AsyncMock(return_value=True))
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())
    db = MagicMock(commit=AsyncMock(side_effect=RuntimeError("commit failed")), rollback=AsyncMock())
    with pytest.raises(RuntimeError, match="commit failed"):
        await routes.delete_document(document, project, MagicMock(), db)
    assert load_original(project, document) == b"source"
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("disk_failure", [False, True])
async def test_delete_storage_and_sql_lifecycle(original_routes, monkeypatch, disk_failure):
    routes = original_routes
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    project, document = uuid.uuid4(), uuid.uuid4()
    save_original(str(project), str(document), b"source")
    vectors = MagicMock()
    monkeypatch.setattr("pipelines.embeddings.delete_document_chunks", vectors)
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())
    if disk_failure:
        monkeypatch.setattr(routes, "delete_original", MagicMock(side_effect=OSError("disk error")))
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add(Document(id=document, project_id=project, filename="test.txt", file_type="text/plain", storage_path="test", status="failed"))
            await db.commit()
            if disk_failure:
                with pytest.raises(OSError, match="disk error"):
                    await routes.delete_document(str(document), str(project), MagicMock(), db)
            else:
                assert await routes.delete_document(str(document), str(project), MagicMock(), db) == {"deleted": True}
        async with sessions() as db:
            assert (await db.get(Document, document) is not None) == disk_failure
        assert original_path(str(project), str(document)).exists() == disk_failure
        if disk_failure:
            vectors.assert_not_called()
            assert load_original(str(project), str(document)) == b"source"
        else:
            vectors.assert_called_once_with(str(document))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_sql_failure_marks_removed_evidence_retryable(original_routes, monkeypatch):
    routes = original_routes
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    project, document = uuid.uuid4(), uuid.uuid4()
    save_original(str(project), str(document), b"source")
    vectors = MagicMock()
    monkeypatch.setattr("pipelines.embeddings.delete_document_chunks", vectors)
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add(Document(id=document, project_id=project, filename="test.txt", file_type="text/plain", storage_path="test", status="processed"))
            await db.commit()
            real_commit = db.commit
            attempts = 0
            async def fail_once():
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("commit failed")
                await real_commit()
            monkeypatch.setattr(db, "commit", fail_once)
            with pytest.raises(RuntimeError, match="commit failed"):
                await routes.delete_document(str(document), str(project), MagicMock(), db)
        vectors.assert_called_once_with(str(document))
        assert load_original(str(project), str(document)) == b"source"
        async with sessions() as db:
            row = await db.get(Document, document)
            assert row.status == "failed"
            assert row.processed_at is None
            assert "evidence cleanup" in row.error_message
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retry_replacement_failure_restores_original(original_routes, monkeypatch):
    from io import BytesIO
    from starlette.datastructures import Headers, UploadFile
    routes = original_routes
    project, document = str(uuid.uuid4()), str(uuid.uuid4())
    save_original(project, document, b"source")
    monkeypatch.setattr(routes.doc_service, "lock_document_for_mutation", AsyncMock(side_effect=[Document(status="failed", file_type="text/plain"), Document(status="failed", file_type="text/plain")]))
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    db = MagicMock(commit=AsyncMock(side_effect=RuntimeError("commit failed")), rollback=AsyncMock())
    file = UploadFile(BytesIO(b"replacement"), filename="source.txt", headers=Headers({"content-type": "text/plain"}))
    request = MagicMock(form=AsyncMock(return_value={"file": file}))
    with pytest.raises(RuntimeError, match="commit failed"):
        await routes.retry_document(document, request, Response(), project, MagicMock(), db)
    assert load_original(project, document) == b"source"
    started.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("loser", ["delete", "retry"])
@pytest.mark.parametrize("winner", ["delete", "retry", "completed_retry", "failed_retry"])
@pytest.mark.parametrize("has_original", [False, True])
async def test_rollback_recovery_preserves_winning_mutation(original_routes, tmp_path, monkeypatch, loser, winner, has_original):
    from datetime import datetime, timezone
    from io import BytesIO
    from starlette.datastructures import Headers, UploadFile
    routes = original_routes
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'recovery.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    project, document = uuid.uuid4(), uuid.uuid4()
    if has_original:
        save_original(str(project), str(document), b"initial source")
    monkeypatch.setattr("pipelines.embeddings.delete_document_chunks", MagicMock())
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)

    def replacement(content):
        file = UploadFile(BytesIO(content), filename="source.txt", headers=Headers({"content-type": "text/plain"}))
        return MagicMock(form=AsyncMock(return_value={"file": file}))

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add(Document(id=document, project_id=project, filename="source.txt", file_type="text/plain", storage_path="test", status="failed"))
            await db.commit()
            real_rollback = db.rollback
            interleaved = False

            async def rollback_then_winner():
                nonlocal interleaved
                await real_rollback()
                if interleaved:
                    return
                interleaved = True
                # This request wins the lock released by the losing rollback,
                # before the losing request begins its compensation.
                async with sessions() as winning_db:
                    if winner == "delete":
                        await routes.delete_document(str(document), str(project), MagicMock(), winning_db)
                    else:
                        await routes.retry_document(str(document), replacement(b"winning source"), Response(), str(project), MagicMock(), winning_db)
                        if winner == "completed_retry":
                            row = await winning_db.get(Document, document)
                            row.status = "processed"
                            row.processed_at = datetime.now(timezone.utc)
                            await winning_db.commit()
                        elif winner == "failed_retry":
                            # Same terminal state as before the losing request:
                            # state labels alone cannot identify this new run.
                            row = await winning_db.get(Document, document)
                            row.status = "failed"
                            row.error_message = None
                            row.processed_at = None
                            await winning_db.commit()

            monkeypatch.setattr(db, "rollback", rollback_then_winner)
            monkeypatch.setattr(db, "commit", AsyncMock(side_effect=RuntimeError("losing commit failed")))
            with pytest.raises(RuntimeError, match="losing commit failed"):
                if loser == "delete":
                    await routes.delete_document(str(document), str(project), MagicMock(), db)
                else:
                    await routes.retry_document(str(document), replacement(b"losing source"), Response(), str(project), MagicMock(), db)
            assert interleaved
        async with sessions() as db:
            row = await db.get(Document, document)
            if winner == "delete":
                assert row is None
                assert not original_path(str(project), str(document)).exists()
                started.assert_not_called()
            else:
                assert row.status == ({"completed_retry": "processed", "failed_retry": "failed"}.get(winner, "pending"))
                assert row.error_message is None
                assert load_original(str(project), str(document)) == b"winning source"
                started.assert_called_once()
                assert started.call_args.args[2] == b"winning source"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_retry_starts_one_job_and_blocks_delete(original_routes, tmp_path, monkeypatch):
    import asyncio
    routes = original_routes
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'isolated.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    project, document = uuid.uuid4(), uuid.uuid4()
    save_original(str(project), str(document), b"source")
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add(Document(id=document, project_id=project, filename="test.txt", file_type="text/plain", storage_path="test", status="failed"))
            await db.commit()
        async def retry():
            async with sessions() as db:
                try:
                    return await routes.retry_document(str(document), Request({"type": "http", "method": "POST", "headers": []}), Response(), str(project), MagicMock(), db)
                except (HTTPException, AppError) as exc:
                    await db.rollback()
                    return exc.status_code
        results = await asyncio.gather(retry(), retry())
        assert sum(isinstance(result, dict) for result in results) == 1
        assert 409 in results
        assert started.call_count == 1
        async with sessions() as db:
            with pytest.raises(HTTPException) as exc:
                await routes.delete_document(str(document), str(project), MagicMock(), db)
            assert exc.value.status_code == 409
        async with sessions() as db:
            row = await db.get(Document, document)
            assert row.status == "pending"
            assert await routes.doc_service.lock_document_for_mutation(db, str(document), str(uuid.uuid4())) is None
        async with sessions() as db:
            await db.delete(await db.get(Document, document))
            await db.commit()
        assert await retry() == 404
        assert started.call_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation_fails", [False, True])
async def test_cancelled_mutation_finishes_before_session_closes(original_routes, mutation_fails):
    import asyncio
    entered, release = asyncio.Event(), asyncio.Event()
    finished = []
    async def mutation():
        entered.set()
        await release.wait()
        finished.append("committed and queued")
        if mutation_fails:
            raise RuntimeError("mutation failed")
    task = asyncio.create_task(original_routes._finish_mutation(mutation()))
    await entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished == ["committed and queued"]


def test_failed_original_replace_keeps_prior_file(original_routes, monkeypatch):
    from services.documents import storage
    project, document = str(uuid.uuid4()), str(uuid.uuid4())
    save_original(project, document, b"source")
    monkeypatch.setattr(storage.os, "replace", MagicMock(side_effect=OSError("disk error")))
    with pytest.raises(OSError, match="disk error"):
        save_original(project, document, b"replacement")
    assert load_original(project, document) == b"source"
    assert list(original_path(project, document).parent.iterdir()) == [original_path(project, document)]
