"""Deployment-specific paths and explicitly selected local embeddings."""

from io import BytesIO
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import UploadFile

from core.config import Settings
from core.security import User
from pipelines.embeddings import embedding_function as embeddings


def test_local_provider_requires_matching_model_and_dimensions():
    config = Settings(_env_file=None, EMBEDDING_PROVIDER="local", EMBEDDING_MODEL="all-MiniLM-L6-v2")
    assert config.EMBEDDING_PROVIDER == "local"
    for overrides in ({"EMBEDDING_MODEL": "wrong"}, {"EMBEDDING_OUTPUT_DIM": 768}):
        values = {"EMBEDDING_PROVIDER": "local", "EMBEDDING_MODEL": "all-MiniLM-L6-v2", **overrides}
        with pytest.raises(ValueError):
            Settings(_env_file=None, **values)


def test_local_embeddings_use_cpu_and_same_space_for_query_and_document(monkeypatch):
    import chromadb.utils.embedding_functions as chroma_functions
    from tokenizers import Tokenizer, models, pre_tokenizers

    calls = []

    class FakeONNX:
        def __init__(self, preferred_providers):
            assert preferred_providers == ["CPUExecutionProvider"]
            self.tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0, "example": 1}, unk_token="[UNK]"))
            self.tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()

        def __call__(self, texts):
            calls.append(texts)
            return [[0.5] * 384 for _ in texts]

    monkeypatch.setattr(chroma_functions, "ONNXMiniLM_L6_V2", FakeONNX)
    monkeypatch.setattr(embeddings.settings, "EMBEDDING_PROVIDER", "local")
    embeddings.reset_embedding_function_cache()
    try:
        for task in (embeddings.TASK_DOCUMENT, embeddings.TASK_QUERY):
            function = embeddings.get_embedding_function(task)
            assert len(function(["example"])[0]) == 384
            with pytest.raises(embeddings.EmbeddingError):
                function([])
        assert calls == [["initialize"], ["example"], ["initialize"], ["example"]]
        vectors = function([" ".join(["example"] * 300)])
        assert len(vectors) == 1
        assert [len(window.split()) for window in calls[-1]] == [254, 46]
        assert sum(float(value) ** 2 for value in vectors[0]) == pytest.approx(1)
    finally:
        embeddings.reset_embedding_function_cache()


@pytest.mark.asyncio
async def test_agent_memory_uses_explicit_local_provider(monkeypatch):
    from services import embeddings as service
    from core.config import settings

    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(embeddings, "get_embedding_function", lambda: lambda texts: [[0.1] * 384 for _ in texts])
    assert len(await service.embed_text("memory")) == 384


@pytest.mark.asyncio
async def test_uploaded_meeting_uses_configured_writable_directory(monkeypatch, tmp_path):
    from core.config import settings
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from routers import meetings
    from services import google_meet

    target = tmp_path / "persistent" / "meetings"
    monkeypatch.setattr(meetings.settings, "MEET_AUDIO_DIR", str(target))
    transcribe = Mock(return_value="Meeting transcript")
    monkeypatch.setattr(google_meet, "transcribe_audio", transcribe)
    monkeypatch.setattr(google_meet, "analyze_transcript", AsyncMock(return_value={"summary": "Summary"}))
    monkeypatch.setattr(meetings, "write_audit_log", AsyncMock())
    result = await meetings.analyze_meeting_audio(
        file=UploadFile(filename="meeting.webm", file=BytesIO(b"audio")),
        project_id="550e8400-e29b-41d4-a716-446655440001", user=User(id="user"), db=AsyncMock(),
    )
    saved = list(target.glob("*.webm"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"audio"
    transcribe.assert_called_once_with(str(saved[0]))
    assert result["summary"] == "Summary"
