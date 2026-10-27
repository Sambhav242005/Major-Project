"""Offline model/decoder contracts and media evidence lifecycle regressions."""
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings
from db.models import Document, DocumentChunk
from db.session import Base
from pipelines import media
from pipelines.chunking import chunk_pages
from pipelines.embeddings import embedding_function as embeddings
from pipelines.parser import parse_document
from routers.documents.validation import UploadValidationError, validate_upload


@pytest.fixture
def media_runtime(monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_INGESTION_ENABLED", True)
    monkeypatch.setattr(settings, "WHISPER_BASE_URL", "http://whisper.test/v1")
    monkeypatch.setattr(settings, "WHISPER_API_KEY", "private-whisper-key")
    monkeypatch.setattr(settings, "VLM_MODEL", "configured-vision-model")
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setattr(settings, "MEDIA_MAX_FRAMES", 3)
    monkeypatch.setattr(media.shutil, "which", lambda executable: executable)
    calls, paths = [], []
    config = {"duration": 30, "audio": True, "video": True, "done": True,
              "segments": [{"text": "Project launch approved", "start": 1.5, "end": 3.5}]}

    def decoder(arguments, deadline):
        paths.append(arguments)
        if arguments[0] == "ffprobe":
            streams = ([{"codec_type": "audio"}] if config["audio"] else [])
            if config["video"]:
                streams.append({"codec_type": "video", "width": 640, "height": 360})
            return json.dumps({"format": {"duration": config["duration"]}, "streams": streams}).encode()
        if arguments[-1] == "pipe:1":
            return b"jpeg-frame-" + arguments[arguments.index("-ss") + 1].encode()
        Path(arguments[-1]).write_bytes(b"RIFF simulated decoded wav")
        return b""

    def handler(request):
        calls.append(request)
        if request.url.path == "/v1/audio/transcriptions":
            assert request.headers["authorization"] == "Bearer private-whisper-key"
            return httpx.Response(200, json={"segments": config["segments"]})
        payload = json.loads(request.content)
        assert payload["model"] == "configured-vision-model"
        assert payload["messages"][0]["images"]
        return httpx.Response(200, json={"done": config["done"], "message": {"content": "Launch slide visible"}})

    client_type = httpx.Client
    monkeypatch.setattr(media, "_run", decoder)
    monkeypatch.setattr(media.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs))
    return config, calls, paths


def test_audio_transcript_retains_real_segment_times_and_temp_cleanup(media_runtime):
    _, calls, commands = media_runtime
    pages = parse_document(b"RIFF audio", "../../untrusted.wav", "audio/wav")
    assert len(pages) == 1 and pages[0]["text"] == "Project launch approved"
    assert pages[0]["source_location"]["start_seconds"] == 1.5
    assert pages[0]["source_location"]["end_seconds"] == 3.5
    assert pages[0]["source_location"]["machine_generated"] is True
    assert b'verbose_json' in calls[0].content and b'timestamp_granularities[]' in calls[0].content
    assert not Path(commands[0][-1]).exists()
    assert "untrusted" not in " ".join(commands[0])


def test_video_combines_transcript_with_bounded_timestamped_frames(media_runtime):
    _, calls, _ = media_runtime
    pages = parse_document(b"video", "video.mp4", "video/mp4")
    assert len(calls) == 4
    assert [p["source_location"]["start_seconds"] for p in pages] == [0, 1.5, 10, 20]
    assert {p["source_location"]["kind"] for p in pages} == {"transcript", "video_frame"}
    chunks = chunk_pages(pages)
    assert len(chunks) == 4
    assert all(c["source_location"] and c["page_number"] is None for c in chunks)


def test_silent_video_uses_vlm_without_inventing_transcription(media_runtime):
    config, calls, _ = media_runtime
    config["audio"] = False
    pages = parse_document(b"video", "video.webm", "video/webm")
    assert len(calls) == 3 and all(p["source_location"]["kind"] == "video_frame" for p in pages)


def test_media_duration_limit_precedes_model_calls(media_runtime):
    config, calls, _ = media_runtime
    config["duration"] = settings.MEDIA_MAX_DURATION_SECONDS + 1
    with pytest.raises(media.MediaError, match="duration limit"):
        parse_document(b"audio", "a.wav", "audio/wav")
    assert calls == []


@pytest.mark.parametrize("segments", [None, [{"text": "bad", "start": -1, "end": 2}],
                                     [{"text": "bad", "start": 1, "end": 900}],
                                     [{"text": "bad", "start": "nan", "end": 2}]])
def test_whisper_requires_valid_timestamped_segments(media_runtime, segments):
    config, _, _ = media_runtime
    config["segments"] = segments
    with pytest.raises(media.MediaError):
        parse_document(b"audio", "a.wav", "audio/wav")


def test_incomplete_vlm_fails_document_instead_of_indexing_partial_text(media_runtime):
    config, _, _ = media_runtime
    config["done"] = False
    with pytest.raises(media.MediaError, match="incomplete"):
        parse_document(b"video", "a.mp4", "video/mp4")


def test_media_upload_gate_and_magic_bytes(media_runtime, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_INGESTION_ENABLED", False)
    with pytest.raises(UploadValidationError, match="disabled"):
        validate_upload(b"RIFF\x00\x00\x00\x00WAVE", "a.wav", "audio/wav")
    monkeypatch.setattr(settings, "MEDIA_INGESTION_ENABLED", True)
    assert validate_upload(b"RIFF\x00\x00\x00\x00WAVE", "a.wav", "audio/wav").category == "audio"
    with pytest.raises(UploadValidationError, match="does not look"):
        validate_upload(b"fake wav", "a.wav", "audio/wav")


def test_ollama_embeddinggemma2_native_batch_contract(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "embeddinggemma-2:740m")
    monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 1)
    monkeypatch.setattr(settings, "EMBEDDING_OUTPUT_DIM", None)
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://ollama.test")

    def post(url, headers, payload, provider):
        calls.append((url, payload, provider))
        return {"embeddings": [[3, 4]]}

    monkeypatch.setattr(embeddings, "_post_json", post)
    vectors = embeddings.OllamaEmbeddingFunction()(["one", "two"])
    assert list(vectors[0]) == pytest.approx([0.6, 0.8])
    assert list(vectors[1]) == pytest.approx([0.6, 0.8])
    assert len(calls) == 2 and calls[0][0].endswith("/api/embed")
    assert calls[0][1] == {"model": "embeddinggemma-2:740m", "input": ["one"], "truncate": False}
    monkeypatch.setattr(embeddings, "_post_json", lambda *args: {"embeddings": []})
    with pytest.raises(embeddings.EmbeddingError, match="counts"):
        embeddings.OllamaEmbeddingFunction()(["one"])


async def test_media_normal_pipeline_persists_source_locations(media_runtime, monkeypatch):
    from pipelines.ingestion.runner import ingest_document
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    captured = []
    monkeypatch.setattr("pipelines.ingestion.pipeline.upsert_chunks", lambda chunks, *args: captured.extend(chunks) or [f"v{i}" for i in range(len(chunks))])
    monkeypatch.setattr("pipelines.embeddings.delete_document_chunks", lambda *args: None)
    monkeypatch.setattr("pipelines.entity_extraction.extract_entities_from_chunks", AsyncMock(return_value=0))
    monkeypatch.setattr("services.webhooks.fire_event", AsyncMock())
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        identifier, project = uuid.uuid4(), uuid.uuid4()
        async with factory() as db:
            db.add(Document(id=identifier, project_id=project, filename="a.wav", file_type="audio/wav", storage_path="private", status="pending"))
            await db.commit()
        await ingest_document(factory, str(identifier), b"audio")
        async with factory() as db:
            assert (await db.get(Document, identifier)).status == "processed"
            chunks = (await db.execute(select(DocumentChunk))).scalars().all()
            assert chunks[0].source_location["start_seconds"] == 1.5
            assert captured[0]["source_location"] == chunks[0].source_location
    finally:
        await engine.dispose()
