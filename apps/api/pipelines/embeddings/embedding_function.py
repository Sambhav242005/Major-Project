"""Embedding providers.

Two providers are supported, selected by ``settings.EMBEDDING_PROVIDER``:

``openai`` (default)
    Any OpenAI-compatible ``POST {EMBEDDING_BASE_URL}/embeddings`` endpoint
    (Ollama, Groq, OpenAI, Gemini's own OpenAI-compat layer).

``gemini``
    Google Gemini's *native* API, which is **not** OpenAI-compatible:
    ``POST {GEMINI_BASE_URL}/models/{EMBEDDING_MODEL}:batchEmbedContents`` with an
    ``x-goog-api-key`` header and a ``{"requests": [...]}`` body.

Two Gemini-specific details drive this module's design:

1. ``:embedContent`` **aggregates** several inputs into a *single* embedding, so a
   naive list-of-strings call would return one vector for N texts and silently
   corrupt the index. ``:batchEmbedContents`` returns one embedding per request.
2. Gemini supports asymmetric retrieval via ``taskType`` — documents are embedded
   as ``RETRIEVAL_DOCUMENT`` and search queries as ``RETRIEVAL_QUERY``. That means
   ingest and query need *different* embedding functions, which is why
   :func:`get_embedding_function` is task-scoped.

References: https://ai.google.dev/gemini-api/docs/embeddings
"""

import logging
import math
import time

import chromadb
import httpx

from core.config import EMBEDDING_PROVIDERS, settings
from core.errors import AppError

logger = logging.getLogger(__name__)

# Task of the text being embedded. Drives Gemini's taskType.
TASK_DOCUMENT = "document"
TASK_QUERY = "query"
EMBEDDING_TASKS = frozenset({TASK_DOCUMENT, TASK_QUERY})

_GEMINI_TASK_TYPES = {
    TASK_DOCUMENT: "RETRIEVAL_DOCUMENT",
    TASK_QUERY: "RETRIEVAL_QUERY",
}

# Gemini always returns unit-length vectors at the default dimension, and
# gemini-embedding-2+ auto-normalizes truncated dimensions too. Older
# gemini-embedding-001 does NOT, so we normalize those ourselves.
_GEMINI_EMBEDDING_2_PREFIX = "gemini-embedding-2"
_GEMINI_DEFAULT_DIM = 3072

# Embeddings 2 dropped the `taskType` field; the documented replacement for
# text-only tasks is a prompt prefix. Prefixes follow the asymmetric retrieval
# examples at https://ai.google.dev/gemini-api/docs/embeddings#task-types-embeddings-2
# `title: none` is what the docs specify when no title is available.
_GEMINI_E2_QUERY_PREFIX = "task: search result | query: "
_GEMINI_E2_DOCUMENT_PREFIX = "title: none | text: "

_RETRY_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 4
_RETRY_BASE_DELAY_SECONDS = 1.0
_TIMEOUT_SECONDS = 60.0
_ERROR_TEXT_LIMIT = 300


class EmbeddingError(AppError):
    """Raised when an embedding provider call fails.

    Inherits :class:`AppError` (not ``RuntimeError``) so FastAPI routes the
    provider's message through ``app_error_handler`` instead of collapsing it
    into an opaque 500 — a 400 from Gemini is operator-actionable.
    """

    status_code = 502
    detail = "Embedding provider request failed"
    error_code = "embedding_failed"


def _truncate(text: str, limit: int = _ERROR_TEXT_LIMIT) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else f"{text[:limit]}..."


def _sleep_before_retry(attempt: int, provider: str, retry_after: str | None) -> None:
    """Back off before retrying. Honours ``Retry-After`` when the API sends it."""
    delay = min(_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)), 30.0)
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    logger.warning(
        "Embedding provider %s rate-limited/erroring, retrying in %.1fs (attempt %d/%d)",
        provider, delay, attempt, _MAX_ATTEMPTS,
    )
    time.sleep(delay)


def _post_json(url: str, headers: dict[str, str], payload: dict, provider: str) -> dict:
    """POST JSON with bounded retries on rate limits and transient 5xx."""
    request_headers = {"Content-Type": "application/json", **headers}
    last_error: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
                resp = client.post(url, headers=request_headers, json=payload)
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == _MAX_ATTEMPTS:
                break
            logger.warning("Embedding provider %s request failed: %s", provider, exc)
            _sleep_before_retry(attempt, provider, None)
            continue

        if resp.status_code == 200:
            return resp.json()

        detail = f"HTTP {resp.status_code}: {_truncate(resp.text)}"
        last_error = EmbeddingError(f"{provider} embeddings {detail}")

        if resp.status_code not in _RETRY_STATUS_CODES:
            # Client or config error — retrying the same request cannot help.
            raise last_error

        if attempt == _MAX_ATTEMPTS:
            raise EmbeddingError(
                f"{provider} embeddings failed after {_MAX_ATTEMPTS} attempts ({detail})"
            ) from last_error

        _sleep_before_retry(attempt, provider, resp.headers.get("Retry-After"))

    raise EmbeddingError(
        f"{provider} embeddings failed after {_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def gemini_api_key() -> str:
    """Resolve the Gemini key, falling back to the shared embedding key."""
    key = (settings.GEMINI_API_KEY or settings.EMBEDDING_API_KEY).strip()
    if not key:
        raise EmbeddingError(
            "EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY "
            "(or EMBEDDING_API_KEY as a fallback)."
        )
    return key


def _is_embedding_2() -> bool:
    """True for the gemini-embedding-2 family.

    Embeddings 2 differs from gemini-embedding-001 in two ways this module must
    honour: it auto-normalizes truncated dimensions (so we must not renormalize
    them again), and it rejects ``taskType`` (prompt prefixes replace it).
    """
    return settings.EMBEDDING_MODEL.startswith(_GEMINI_EMBEDDING_2_PREFIX)


def _needs_manual_normalization() -> bool:
    """gemini-embedding-001 returns unnormalized vectors below 3072 dims."""
    if _is_embedding_2():
        return False
    dim = settings.EMBEDDING_OUTPUT_DIM
    return dim is not None and dim < _GEMINI_DEFAULT_DIM


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        raise EmbeddingError("Embedding provider returned an all-zero vector")
    return [value / norm for value in vector]


def _reject_empty(texts: list[str], provider: str) -> None:
    """Chroma's EmbeddingFunction wrapper rejects empty result lists.

    Call sites must skip empty work rather than hand us an empty batch; say so
    clearly instead of surfacing Chroma's opaque "non-empty list" ValueError.
    """
    if not texts:
        raise EmbeddingError(
            f"{provider} embedding function called with no input texts; "
            "callers must skip empty work instead of embedding nothing."
        )


class OpenAICompatibleEmbeddingFunction(chromadb.EmbeddingFunction):
    """Embedding function for any OpenAI-compatible /embeddings endpoint.

    ``task`` is accepted for interface parity with the Gemini provider; the
    OpenAI-compatible surface has no notion of a retrieval task type.
    """

    def __init__(self, task: str = TASK_DOCUMENT) -> None:
        self.task = task

    def name(self) -> str:
        return "openai-compatible"

    def _url(self) -> str:
        return f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings"

    def _headers(self) -> dict[str, str]:
        if settings.EMBEDDING_API_KEY:
            return {"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"}
        return {}

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        texts = list(input)
        _reject_empty(texts, "openai")

        payload: dict = {"model": settings.EMBEDDING_MODEL, "input": texts}
        # Opt-in only: not every OpenAI-compatible server accepts `dimensions`.
        if settings.EMBEDDING_OUTPUT_DIM:
            payload["dimensions"] = settings.EMBEDDING_OUTPUT_DIM

        data = _post_json(self._url(), self._headers(), payload, provider="openai")
        try:
            return [item["embedding"] for item in data["data"]]
        except (KeyError, TypeError) as exc:
            raise EmbeddingError(
                f"Unexpected /embeddings response shape from {self._url()}: "
                f"{_truncate(str(data))}"
            ) from exc


class GeminiEmbeddingFunction(chromadb.EmbeddingFunction):
    """Gemini embeddings via the native ``:batchEmbedContents`` endpoint."""

    def __init__(self, task: str = TASK_DOCUMENT) -> None:
        if task not in EMBEDDING_TASKS:
            raise ValueError(
                f"Unknown embedding task {task!r}; expected one of {sorted(EMBEDDING_TASKS)}"
            )
        self.task = task

    def name(self) -> str:
        return "gemini-batch"

    @property
    def task_type(self) -> str:
        return _GEMINI_TASK_TYPES[self.task]

    def _url(self) -> str:
        base = settings.GEMINI_BASE_URL.rstrip("/")
        return f"{base}/models/{settings.EMBEDDING_MODEL}:batchEmbedContents"

    def _prepare_text(self, text: str) -> str:
        """Apply the task signal for the configured model.

        gemini-embedding-001 takes it via ``taskType`` (left untouched here).
        gemini-embedding-2 has no ``taskType`` — it wants the task in the text.
        """
        if not _is_embedding_2():
            return text
        if self.task == TASK_QUERY:
            return f"{_GEMINI_E2_QUERY_PREFIX}{text}"
        return f"{_GEMINI_E2_DOCUMENT_PREFIX}{text}"

    def _build_request(self, text: str) -> dict:
        request: dict = {
            "model": f"models/{settings.EMBEDDING_MODEL}",
            "content": {"parts": [{"text": self._prepare_text(text)}]},
        }
        # Sending taskType to Embeddings 2 is a hard 400; _prepare_text carries
        # the task signal for that model instead.
        if not _is_embedding_2() and self.task in _GEMINI_TASK_TYPES:
            request["taskType"] = self.task_type
        if settings.EMBEDDING_OUTPUT_DIM:
            request["output_dimensionality"] = settings.EMBEDDING_OUTPUT_DIM
        return request

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        texts = list(input)
        _reject_empty(texts, "gemini")

        headers = {"x-goog-api-key": gemini_api_key()}
        batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)

        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = [self._build_request(text) for text in texts[start:start + batch_size]]
            data = _post_json(self._url(), headers, {"requests": batch}, provider="gemini")

            embeddings = data.get("embeddings") or []
            if len(embeddings) != len(batch):
                raise EmbeddingError(
                    f"Gemini returned {len(embeddings)} embeddings for {len(batch)} inputs; "
                    "refusing to index mismatched vectors."
                )
            try:
                vectors.extend(embedding["values"] for embedding in embeddings)
            except (KeyError, TypeError) as exc:
                raise EmbeddingError(
                    f"Unexpected :batchEmbedContents response shape from {self._url()}: "
                    f"{_truncate(str(data))}"
                ) from exc

        if _needs_manual_normalization():
            vectors = [_l2_normalize(vector) for vector in vectors]

        return vectors


_PROVIDER_CLASSES = {
    "gemini": GeminiEmbeddingFunction,
    "openai": OpenAICompatibleEmbeddingFunction,
}

_embedding_functions: dict[tuple[str, str], chromadb.EmbeddingFunction] = {}


def reset_embedding_function_cache() -> None:
    """Drop cached embedding functions (used by tests and config reloads)."""
    _embedding_functions.clear()


def get_embedding_function(task: str = TASK_DOCUMENT) -> chromadb.EmbeddingFunction:
    """Return the embedding function for ``task``.

    ``task`` is ``TASK_DOCUMENT`` when embedding chunks for storage and
    ``TASK_QUERY`` when embedding a search query — Gemini needs the matching
    ``taskType`` for each.

    This never returns ``None``. A failing or misconfigured provider must raise,
    because falling back to Chroma's built-in embedding function would write
    vectors from a different model into the same collection and make retrieval
    silently wrong.
    """
    if task not in EMBEDDING_TASKS:
        raise ValueError(
            f"Unknown embedding task {task!r}; expected one of {sorted(EMBEDDING_TASKS)}"
        )

    provider = settings.EMBEDDING_PROVIDER
    if provider not in _PROVIDER_CLASSES:
        raise EmbeddingError(
            f"Unknown EMBEDDING_PROVIDER {provider!r}; "
            f"expected one of {sorted(EMBEDDING_PROVIDERS)}"
        )

    key = (provider, task)
    embedding_fn = _embedding_functions.get(key)
    if embedding_fn is None:
        embedding_fn = _PROVIDER_CLASSES[provider](task=task)
        _embedding_functions[key] = embedding_fn
    return embedding_fn
