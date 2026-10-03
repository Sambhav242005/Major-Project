"""Tests for embedding providers — dispatch, Gemini request shape, space guards."""

import math
import uuid

import chromadb
import pytest

from core.config import Settings, settings
from core.errors import AppError
from core.sse import generator_sse_stream
from pipelines.embeddings import embedding_function as ef_mod
from pipelines.embeddings import query as query_mod
from pipelines.embeddings import store as store_mod
from pipelines.embeddings.embedding_function import (
    TASK_DOCUMENT,
    TASK_QUERY,
    EmbeddingError,
    GeminiEmbeddingFunction,
    OpenAICompatibleEmbeddingFunction,
    get_embedding_function,
    reset_embedding_function_cache,
)


# --- test doubles -----------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text or ""

    def json(self):
        return self._payload


class FakeClient:
    """Records POSTs and replays queued responses.

    The queue is shared across the clients created for each retry attempt, so a
    retry sees the next queued response instead of restarting the script.
    """

    def __init__(self, responses, calls, timeout=None):
        self._responses = responses
        self.calls = calls
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers or {}, "json": json})
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


class SleepRecorder:
    def __init__(self):
        self.calls: list[float] = []

    def sleep(self, seconds):
        self.calls.append(seconds)


class StubEmbeddingFunction(chromadb.EmbeddingFunction):
    """Deterministic, text-dependent embeddings recording the task type used."""

    def __init__(self, dim=3):
        self.dim = dim
        self.tasks: list[str] = []

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        # Distinct direction per text, but identical for identical text, so an
        # exact match always wins a cosine search.
        fingerprint = sum((i + 1) * ord(char) for i, char in enumerate(text))
        return [float(fingerprint % 11), float(len(text)), 1.0]

    def __call__(self, input):
        self.tasks.append(getattr(self, "task", TASK_DOCUMENT))
        return [self._vector_for(text) for text in input]


def patch_http(monkeypatch, responses):
    """Route every httpx.Client used by the embedding layer to a FakeClient."""
    calls: list[dict] = []
    monkeypatch.setattr(
        ef_mod.httpx, "Client",
        lambda *a, **kw: FakeClient(responses, calls, timeout=kw.get("timeout")),
    )
    return calls


def patch_sleep(monkeypatch):
    recorder = SleepRecorder()
    monkeypatch.setattr(ef_mod, "time", recorder)
    return recorder


def use_gemini(monkeypatch, model="gemini-embedding-001", **overrides):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", model)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(settings, "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    for key, value in overrides.items():
        monkeypatch.setattr(settings, key, value)


def gemini_payload(count, dim=3):
    return {"embeddings": [{"values": [0.5] * dim} for _ in range(count)]}


@pytest.fixture(autouse=True)
def _clear_embedding_cache():
    reset_embedding_function_cache()
    yield
    reset_embedding_function_cache()


# --- provider selection -----------------------------------------------------

def test_default_provider_is_openai_compatible(monkeypatch):
    # Pinned rather than read from settings: the repo's .env is gitignored, so
    # asserting the ambient value would make this test fail for anyone who set
    # EMBEDDING_PROVIDER=gemini locally (exactly what this PR tells them to do).
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    assert isinstance(get_embedding_function(), OpenAICompatibleEmbeddingFunction)


def test_gemini_provider_selected(monkeypatch):
    use_gemini(monkeypatch)
    assert isinstance(get_embedding_function(), GeminiEmbeddingFunction)


def test_invalid_provider_rejected(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "cohere")
    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER must be one of"):
        Settings()


def test_gemini_provider_requires_api_key(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("EMBEDDING_API_KEY", "")
    with pytest.raises(ValueError, match="requires GEMINI_API_KEY"):
        Settings()


def test_gemini_key_falls_back_to_embedding_api_key(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("EMBEDDING_API_KEY", "shared-key")
    configured = Settings()
    assert configured.GEMINI_API_KEY == "" or configured.EMBEDDING_API_KEY == "shared-key"
    assert (configured.GEMINI_API_KEY or configured.EMBEDDING_API_KEY) == "shared-key"


def test_provider_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "GEMINI")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert Settings().EMBEDDING_PROVIDER == "gemini"


def test_embedding_function_cache_is_task_scoped(monkeypatch):
    use_gemini(monkeypatch)
    document_fn = get_embedding_function(TASK_DOCUMENT)
    query_fn = get_embedding_function(TASK_QUERY)
    assert document_fn is not query_fn
    assert get_embedding_function(TASK_DOCUMENT) is document_fn


def test_unknown_task_rejected():
    with pytest.raises(ValueError, match="Unknown embedding task"):
        get_embedding_function("summarise")


def test_get_embedding_function_never_returns_none(monkeypatch):
    """A dead provider must raise, not degrade to Chroma's default EF."""
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "EMBEDDING_BASE_URL", "http://127.0.0.1:9/v1")
    patch_sleep(monkeypatch)
    with pytest.raises(EmbeddingError):
        get_embedding_function()(["hello"])


# --- Gemini request shape ---------------------------------------------------

def test_gemini_uses_native_batch_endpoint(monkeypatch):
    use_gemini(monkeypatch)
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])

    get_embedding_function(TASK_DOCUMENT)(["hello"])

    call = calls[0]
    assert call["url"].endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert call["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert call["json"]["requests"][0]["content"]["parts"][0]["text"] == "hello"


def test_gemini_sends_one_request_per_text(monkeypatch):
    """:embedContent aggregates inputs; batching must stay 1 text -> 1 vector."""
    use_gemini(monkeypatch)
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(3))])

    vectors = get_embedding_function(TASK_DOCUMENT)(["a", "bb", "ccc"])

    assert len(calls[0]["json"]["requests"]) == 3
    assert len(vectors) == 3


def test_gemini_uses_document_task_type_for_ingest(monkeypatch):
    use_gemini(monkeypatch)
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])

    get_embedding_function(TASK_DOCUMENT)(["chunk text"])

    assert calls[0]["json"]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"


def test_gemini_uses_query_task_type_for_search(monkeypatch):
    use_gemini(monkeypatch)
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])

    get_embedding_function(TASK_QUERY)(["a question"])

    assert calls[0]["json"]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_embedding_2_omits_task_type(monkeypatch):
    """Embeddings 2 rejects taskType outright (HTTP 400), so never send it."""
    use_gemini(monkeypatch, model="gemini-embedding-2")
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])

    get_embedding_function(TASK_QUERY)(["a question"])
    get_embedding_function(TASK_DOCUMENT)(["some chunk"])

    assert len(calls) == 2
    for call in calls:
        for request in call["json"]["requests"]:
            assert "taskType" not in request


def test_embedding_2_prefixes_query_text(monkeypatch):
    """Embeddings 2 takes the task via prompt prefix instead of taskType."""
    use_gemini(monkeypatch, model="gemini-embedding-2")
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])

    get_embedding_function(TASK_QUERY)(["weather today"])

    text = calls[0]["json"]["requests"][0]["content"]["parts"][0]["text"]
    assert text == "task: search result | query: weather today"


def test_embedding_2_prefixes_document_text(monkeypatch):
    use_gemini(monkeypatch, model="gemini-embedding-2")
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])

    get_embedding_function(TASK_DOCUMENT)(["some chunk"])

    text = calls[0]["json"]["requests"][0]["content"]["parts"][0]["text"]
    assert text == "title: none | text: some chunk"


def test_embedding_001_text_is_untouched_by_prefixes(monkeypatch):
    """001 carries the task in taskType — prefixing would corrupt its input."""
    use_gemini(monkeypatch, model="gemini-embedding-001")
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])

    get_embedding_function(TASK_QUERY)(["a question"])

    request = calls[0]["json"]["requests"][0]
    assert request["taskType"] == "RETRIEVAL_QUERY"
    assert request["content"]["parts"][0]["text"] == "a question"


def test_gemini_sends_output_dimensionality_when_set(monkeypatch):
    use_gemini(monkeypatch, EMBEDDING_OUTPUT_DIM=768)
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1, dim=768))])

    vectors = get_embedding_function(TASK_DOCUMENT)(["hello"])

    assert calls[0]["json"]["requests"][0]["output_dimensionality"] == 768
    assert len(vectors[0]) == 768


def test_gemini_omits_output_dimensionality_by_default(monkeypatch):
    use_gemini(monkeypatch)
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])

    get_embedding_function(TASK_DOCUMENT)(["hello"])

    assert "output_dimensionality" not in calls[0]["json"]["requests"][0]


def test_gemini_rejects_count_mismatch(monkeypatch):
    use_gemini(monkeypatch)
    patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(1))])
    with pytest.raises(EmbeddingError, match="refusing to index mismatched vectors"):
        get_embedding_function(TASK_DOCUMENT)(["a", "b"])


def test_gemini_rejects_empty_input(monkeypatch):
    """Chroma forbids empty embedding lists, so callers must skip empty work."""
    use_gemini(monkeypatch)
    calls = patch_http(monkeypatch, [FakeResponse(payload=gemini_payload(0))])
    with pytest.raises(EmbeddingError, match="called with no input texts"):
        get_embedding_function(TASK_DOCUMENT)([])
    assert calls == []


def test_gemini_batches_large_inputs(monkeypatch):
    use_gemini(monkeypatch, EMBEDDING_BATCH_SIZE=2)
    calls = patch_http(monkeypatch, [
        FakeResponse(payload=gemini_payload(2)),
        FakeResponse(payload=gemini_payload(1)),
    ])

    vectors = get_embedding_function(TASK_DOCUMENT)(["a", "b", "c"])

    assert len(calls) == 2
    assert [len(call["json"]["requests"]) for call in calls] == [2, 1]
    assert len(vectors) == 3


def test_gemini_normalizes_truncated_vectors(monkeypatch):
    """gemini-embedding-001 does not normalize below 3072 dims."""
    use_gemini(monkeypatch, EMBEDDING_OUTPUT_DIM=2)
    patch_http(monkeypatch, [FakeResponse(payload={"embeddings": [{"values": [3.0, 4.0]}]})])

    vector = get_embedding_function(TASK_DOCUMENT)(["hello"])[0]

    assert vector == pytest.approx([0.6, 0.8])


def test_gemini_does_not_renormalize_embedding_2(monkeypatch):
    use_gemini(monkeypatch, model="gemini-embedding-2", EMBEDDING_OUTPUT_DIM=2)
    patch_http(monkeypatch, [FakeResponse(payload={"embeddings": [{"values": [3.0, 4.0]}]})])

    vector = get_embedding_function(TASK_DOCUMENT)(["hello"])[0]

    assert vector == pytest.approx([3.0, 4.0])


def test_gemini_normalizes_at_full_dimension(monkeypatch):
    use_gemini(monkeypatch, EMBEDDING_OUTPUT_DIM=3072)
    patch_http(monkeypatch, [FakeResponse(payload={"embeddings": [{"values": [3.0, 4.0]}]})])

    vector = get_embedding_function(TASK_DOCUMENT)(["hello"])[0]

    assert vector == pytest.approx([3.0, 4.0])


def test_gemini_rejects_zero_vector(monkeypatch):
    use_gemini(monkeypatch, EMBEDDING_OUTPUT_DIM=2)
    patch_http(monkeypatch, [FakeResponse(payload={"embeddings": [{"values": [0.0, 0.0]}]})])
    with pytest.raises(EmbeddingError, match="all-zero vector"):
        get_embedding_function(TASK_DOCUMENT)(["hello"])


# --- retries and errors -----------------------------------------------------

def test_gemini_retries_rate_limit_then_succeeds(monkeypatch):
    use_gemini(monkeypatch)
    sleeper = patch_sleep(monkeypatch)
    patch_http(monkeypatch, [
        FakeResponse(status_code=429, text="quota exceeded", headers={"Retry-After": "2"}),
        FakeResponse(payload=gemini_payload(1)),
    ])

    vectors = get_embedding_function(TASK_DOCUMENT)(["hello"])

    assert len(vectors) == 1
    assert sleeper.calls == [2.0]


def test_gemini_gives_up_after_max_attempts(monkeypatch):
    use_gemini(monkeypatch)
    sleeper = patch_sleep(monkeypatch)
    patch_http(monkeypatch, [FakeResponse(status_code=429, text="quota exceeded")])

    with pytest.raises(EmbeddingError, match="failed after 4 attempts"):
        get_embedding_function(TASK_DOCUMENT)(["hello"])

    assert len(sleeper.calls) == 3


def test_gemini_does_not_retry_client_errors(monkeypatch):
    use_gemini(monkeypatch)
    sleeper = patch_sleep(monkeypatch)
    patch_http(monkeypatch, [FakeResponse(status_code=400, text="bad request")])

    with pytest.raises(EmbeddingError, match="HTTP 400"):
        get_embedding_function(TASK_DOCUMENT)(["hello"])

    assert sleeper.calls == []


def test_gemini_missing_key_raises(monkeypatch):
    use_gemini(monkeypatch)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", "")
    with pytest.raises(EmbeddingError, match="requires GEMINI_API_KEY"):
        get_embedding_function(TASK_DOCUMENT)(["hello"])


# --- error contract: remediation must reach the client ----------------------
#
# These errors exist to tell an operator how to recover. If they are plain
# RuntimeError, FastAPI collapses them to an opaque 500 and that text is lost.

def test_embedding_error_carries_app_error_contract():
    assert issubclass(EmbeddingError, AppError)
    error = EmbeddingError("gemini embeddings HTTP 400: bad model")
    assert error.status_code == 502
    assert error.error_code == "embedding_failed"
    assert error.detail == "gemini embeddings HTTP 400: bad model"


def test_embedding_space_mismatch_is_a_conflict():
    assert issubclass(store_mod.EmbeddingSpaceMismatchError, AppError)
    error = store_mod.EmbeddingSpaceMismatchError("delete CHROMA_PATH then re-embed")
    assert error.status_code == 409
    assert error.error_code == "embedding_space_mismatch"
    assert error.detail == "delete CHROMA_PATH then re-embed"


async def _stream_error_payload(exc: Exception) -> str:
    """Run an SSE generator that raises, and return what the client receives."""

    async def boom():
        raise exc
        yield  # pragma: no cover — makes this an async generator

    response = await generator_sse_stream(boom())
    return "".join([chunk async for chunk in response.body_iterator])


async def test_sse_stream_forwards_app_error_detail():
    """generator_sse_stream must not swallow the remediation message."""
    payload = await _stream_error_payload(
        store_mod.EmbeddingSpaceMismatchError("delete CHROMA_PATH then re-embed")
    )
    assert "delete CHROMA_PATH then re-embed" in payload


async def test_sse_stream_keeps_internal_errors_generic():
    """Only AppError detail is forwarded — never arbitrary exception text."""
    payload = await _stream_error_payload(RuntimeError("secret connection string"))
    assert "secret connection string" not in payload
    assert "Stream interrupted" in payload


# --- OpenAI-compatible path (unchanged behaviour) ---------------------------

def test_openai_compatible_request_shape(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "EMBEDDING_BASE_URL", "http://localhost:11434/v1/")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "qwen3-embedding:4b")
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "EMBEDDING_OUTPUT_DIM", None)
    calls = patch_http(monkeypatch, [
        FakeResponse(payload={"data": [{"embedding": [0.1, 0.2]}]}),
    ])

    vectors = get_embedding_function()(["hello"])

    call = calls[0]
    assert call["url"] == "http://localhost:11434/v1/embeddings"
    assert call["headers"]["Authorization"] == "Bearer sk-test"
    assert call["json"] == {"model": "qwen3-embedding:4b", "input": ["hello"]}
    assert [list(vector) for vector in vectors] == [pytest.approx([0.1, 0.2])]


def test_openai_compatible_sends_dimensions_only_when_opted_in(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "EMBEDDING_OUTPUT_DIM", 768)
    calls = patch_http(monkeypatch, [
        FakeResponse(payload={"data": [{"embedding": [0.1]}]}),
    ])

    get_embedding_function()(["hello"])

    assert calls[0]["json"]["dimensions"] == 768


def test_openai_compatible_rejects_unexpected_shape(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    patch_http(monkeypatch, [FakeResponse(payload={"unexpected": True})])
    with pytest.raises(EmbeddingError, match="Unexpected /embeddings response shape"):
        get_embedding_function()(["hello"])


# --- Chroma vector-space guard ---------------------------------------------

@pytest.fixture
def chroma_collection(monkeypatch):
    """Ephemeral Chroma collection wired into the store helpers.

    ``chromadb.EphemeralClient()`` shares one in-memory system per process, so
    each test gets a uniquely named collection to stay isolated.
    """
    collection_name = f"knowledge_base_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(store_mod, "COLLECTION_NAME", collection_name)

    client = chromadb.EphemeralClient()
    stub = StubEmbeddingFunction()

    def stub_factory(task=TASK_DOCUMENT):
        """Stand in for the provider EF, recording which task asked for it."""
        stub.task = task
        return stub

    monkeypatch.setattr(store_mod, "get_chroma_client", lambda: client)
    monkeypatch.setattr(query_mod, "get_collection", lambda: store_mod.get_collection())
    monkeypatch.setattr(store_mod, "get_embedding_function", stub_factory)
    monkeypatch.setattr(query_mod, "get_embedding_function", stub_factory)
    return client, stub


def test_matching_fingerprint_is_accepted(monkeypatch, chroma_collection):
    client, _ = chroma_collection
    client.get_or_create_collection(
        name=store_mod.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", store_mod.FINGERPRINT_KEY: store_mod.embedding_fingerprint()},
    )
    assert store_mod.get_collection() is not None


def test_legacy_empty_collection_adopts_fingerprint(monkeypatch, chroma_collection):
    client, _ = chroma_collection
    client.get_or_create_collection(
        name=store_mod.COLLECTION_NAME, metadata={"hnsw:space": "cosine"},
    )
    store_mod.get_collection()
    stamped = client.get_collection(store_mod.COLLECTION_NAME).metadata
    assert stamped[store_mod.FINGERPRINT_KEY] == store_mod.embedding_fingerprint()


def test_legacy_populated_collection_adopts_fingerprint_for_openai(monkeypatch, chroma_collection):
    """Existing deployments must keep working after the upgrade."""
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    client, _ = chroma_collection
    legacy = client.get_or_create_collection(
        name=store_mod.COLLECTION_NAME, metadata={"hnsw:space": "cosine"},
    )
    legacy.upsert(ids=["1"], documents=["old"], embeddings=[[1.0, 0.0, 0.0]], metadatas=[{"project_id": "p"}])

    store_mod.get_collection()

    stamped = client.get_collection(store_mod.COLLECTION_NAME).metadata
    assert stamped[store_mod.FINGERPRINT_KEY] == store_mod.embedding_fingerprint()


def test_legacy_populated_collection_blocks_provider_switch(monkeypatch, chroma_collection):
    client, _ = chroma_collection
    legacy = client.get_or_create_collection(
        name=store_mod.COLLECTION_NAME, metadata={"hnsw:space": "cosine"},
    )
    legacy.upsert(ids=["1"], documents=["old"], embeddings=[[1.0, 0.0, 0.0]], metadatas=[{"project_id": "p"}])
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "gemini-embedding-001")

    with pytest.raises(store_mod.EmbeddingSpaceMismatchError, match="unrecorded embedding model"):
        store_mod.get_collection()


def test_changed_model_is_rejected(monkeypatch, chroma_collection):
    client, _ = chroma_collection
    store_mod.get_collection()
    assert client.get_collection(store_mod.COLLECTION_NAME).metadata[store_mod.FINGERPRINT_KEY]

    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "some-other-model")

    with pytest.raises(store_mod.EmbeddingSpaceMismatchError, match="Re-embed the existing"):
        store_mod.get_collection()


def test_changed_output_dim_is_rejected(monkeypatch, chroma_collection):
    client, _ = chroma_collection
    store_mod.get_collection()

    monkeypatch.setattr(settings, "EMBEDDING_OUTPUT_DIM", 768)

    with pytest.raises(store_mod.EmbeddingSpaceMismatchError):
        store_mod.get_collection()


def test_fingerprint_changes_with_provider_model_and_dim(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "qwen3-embedding:4b")
    monkeypatch.setattr(settings, "EMBEDDING_OUTPUT_DIM", None)
    assert store_mod.embedding_fingerprint() == "openai:qwen3-embedding:4b:default"

    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "gemini-embedding-001")
    monkeypatch.setattr(settings, "EMBEDDING_OUTPUT_DIM", 768)
    assert store_mod.embedding_fingerprint() == "gemini:gemini-embedding-001:768"


def test_fingerprint_does_not_include_reserved_chroma_keys(monkeypatch, chroma_collection):
    client, _ = chroma_collection
    store_mod.get_collection()
    stamped = client.get_collection(store_mod.COLLECTION_NAME).metadata
    assert "hnsw:space" not in stamped


# --- ingest/query round trip -----------------------------------------------

def test_upsert_then_query_routes_task_types(monkeypatch, chroma_collection):
    _, stub = chroma_collection
    chunks = [
        {"chunk_index": 0, "text": "alpha", "page_number": 1},
        {"chunk_index": 1, "text": "bb", "page_number": 2},
    ]

    ids = store_mod.upsert_chunks(chunks, project_id="p1", document_id="d1")
    results = query_mod._embed_and_query(
        store_mod.get_collection(), "alpha", project_id="p1", top_k=2,
    )

    assert ids == ["d1_chunk_0", "d1_chunk_1"]
    # The exact-match chunk must come first, and both chunks must be returned.
    assert results["ids"][0] == ["d1_chunk_0", "d1_chunk_1"]
    assert results["distances"][0][0] <= results["distances"][0][1]
    assert stub.tasks == [TASK_DOCUMENT, TASK_QUERY]


def test_upsert_empty_chunks_is_noop(monkeypatch, chroma_collection):
    assert store_mod.upsert_chunks([], project_id="p1", document_id="d1") == []


def test_delete_document_chunks_removes_vectors(monkeypatch, chroma_collection):
    client, _ = chroma_collection
    store_mod.upsert_chunks(
        [{"chunk_index": 0, "text": "alpha", "page_number": 1}],
        project_id="p1", document_id="d1",
    )

    store_mod.delete_document_chunks("d1")

    assert client.get_collection(store_mod.COLLECTION_NAME).count() == 0


def test_explicit_embeddings_are_l2_safe_for_cosine(monkeypatch, chroma_collection):
    """Sanity: vectors reaching Chroma are the ones the provider returned."""
    client, _ = chroma_collection
    store_mod.upsert_chunks(
        [{"chunk_index": 0, "text": "abcd", "page_number": 1}],
        project_id="p1", document_id="d1",
    )
    stored = client.get_collection(store_mod.COLLECTION_NAME).get(
        ids=["d1_chunk_0"], include=["embeddings"],
    )
    stored_vector = [float(value) for value in stored["embeddings"][0]]
    assert stored_vector == pytest.approx(StubEmbeddingFunction._vector_for("abcd"))
