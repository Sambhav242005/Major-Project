"""Real persistence and scanned-page rendering regressions."""
import io
import uuid
from unittest.mock import AsyncMock

import fitz
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import UploadFile

from core.config import settings
from core.security import User
from db.models import AuditLog, Profile, Project
from db.session import Base


def test_mixed_pdf_rasterizes_scanned_pages_without_ocr_on_text(monkeypatch):
    from pipelines import parser
    calls = []
    def ocr(content, filename):
        assert content.startswith(b"\x89PNG\r\n\x1a\n")
        calls.append(filename)
        return [{"text": "Scanned page recovered", "page_number": 1}]
    monkeypatch.setattr(parser, "parse_image", ocr)
    with fitz.open() as document:
        text_page = document.new_page()
        text_page.insert_text((72, 72), "Existing text layer")
        document.new_page()
        content = document.tobytes()
    result = parser.parse_document(content, "mixed.pdf", "application/pdf")
    assert "Existing text layer" in result[0]["text"]
    assert result[1] == {"text": "Scanned page recovered", "page_number": 2}
    assert calls == ["page_2.png"]


@pytest.mark.asyncio
async def test_meeting_analysis_persists_and_history_is_project_scoped(tmp_path, monkeypatch):
    from routers.meetings import analyze_meeting_audio, list_meetings
    monkeypatch.setattr(settings, "MEET_AUDIO_DIR", str(tmp_path))
    monkeypatch.setattr("services.google_meet.transcribe_audio", lambda _: "Agreed to deliver on Friday.")
    monkeypatch.setattr("services.google_meet.analyze_transcript", AsyncMock(return_value={"summary": "Deliver Friday", "key_points": ["Deadline"], "action_items": ["Deliver"], "sentiment": "positive"}))
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    first, other, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            db.add_all([Profile(id=user_id, full_name="Reviewer"), Project(id=first, name="First"), Project(id=other, name="Other")])
            await db.commit()
            user = User(id=str(user_id), email="reviewer@example.com")
            analysis = await analyze_meeting_audio(UploadFile(io.BytesIO(b"recording"), filename="meeting.wav"), str(first), user, db)
            assert analysis["summary"] == "Deliver Friday"
            assert "audio_path" not in analysis
            db.add(AuditLog(project_id=other, action="meeting.analyzed", meta={"summary": "Private other project"}))
            await db.commit()
        # A fresh session proves this is persisted rather than process memory.
        async with sessions() as db:
            history = await list_meetings(str(first), user, db, 20)
            assert len(history["meetings"]) == 1
            assert history["meetings"][0]["id"] == analysis["id"]
            assert history["meetings"][0]["summary"] == "Deliver Friday"
    finally:
        await engine.dispose()
