"""GitHub repository ingestion (TODO 2.25, Phase 1) — fully offline tests.

Fixture payloads live under ``tests/fixtures/github/``. No test touches the
network: HTTP behaviour is exercised with ``httpx.MockTransport`` and import
jobs run against fixture-backed fake clients over an in-memory SQLite database.
"""

import asyncio
import base64
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.config import settings
from db.models import Document, DocumentChunk, DocumentSource
from db.session import Base
from services.github_import import (
    ImportRejected,
    RepoLimitError,
    filter_tree,
    is_commit_sha,
    parse_repo_url,
    validate_patterns,
    validate_ref,
)
from services.github_import import filters as gh_filters
from services.github_import import jobs as import_jobs
from services.github_import.client import (
    GitHubAuthError,
    GitHubConfigError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRedirectBlocked,
    GitHubUnavailableError,
    HttpxGitHubClient,
    TreeEntry,
    _validate_base_url,
)
from services.github_import.service import (
    ImportTarget,
    PreviewResult,
    build_preview,
    resolve_repository,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "github"
README_SHA = "c1aa1aa2bb2cc3dd4ee5ff60001112223334455a"
DOCS_SHA = "d2bb2cc3dd4ee5f6001122334455aabbccddeeff"
MAIN_PY_SHA = "e3cc3dd4ee5f6001122334455aabbccddeeff00a"
COMMIT_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e"


def _fixture(name: str):
    return json.loads(FIXTURES.joinpath(name).read_text(encoding="utf-8"))


def _blob_payload(sha: str, content: bytes) -> dict:
    return {
        "sha": sha,
        "encoding": "base64",
        "content": base64.b64encode(content).decode("ascii"),
        "size": len(content),
    }


def entry(path: str, size: int | None, sha: str, kind: str = "blob") -> TreeEntry:
    return TreeEntry(path=path, type=kind, sha=sha, size=size)


def _tree_entries() -> list[TreeEntry]:
    fixture_tree = _fixture("tree.json")["tree"]
    return [
        TreeEntry(path=t["path"], type=t["type"], sha=t["sha"], size=t.get("size"))
        for t in fixture_tree
    ]


def _preview(outcome) -> PreviewResult:
    return PreviewResult(
        owner="ok-org",
        repo="ok-repo",
        ref="main",
        commit_sha=COMMIT_SHA,
        files=outcome.included,
        excluded=outcome.excluded,
        total_bytes=outcome.total_bytes,
        tree_entry_count=5,
    )


# ---------------------------------------------------------------------------
# Request validation (repository URL / ref / patterns)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,owner,repo", [
    ("https://github.com/ok-org/ok-repo", "ok-org", "ok-repo"),
    ("https://github.com/ok-org/ok-repo.git", "ok-org", "ok-repo"),
    ("https://github.com/ok-org/ok-repo/tree/main", "ok-org", "ok-repo"),
    ("https://github.com/ok-org/ok-repo/tree/v1.2.3/sub?tab=doc", "ok-org", "ok-repo"),
])
def test_repo_url_parsing_accepts_github_forms(url, owner, repo):
    assert parse_repo_url(url) == (owner, repo)


@pytest.mark.parametrize("url", [
    "http://github.com/ok-org/ok-repo",
    "https://gitlab.com/ok-org/ok-repo",
    "https://github.com/ok-org/../../etc",
    "https://github.com/ok-org",
    "https://github.com/ok-org/ok-repo/extra/deep/tree/main",
    "",
])
def test_repo_url_parsing_rejects_other_hosts_and_traversal(url):
    with pytest.raises(ValueError):
        parse_repo_url(url)


def test_commit_sha_passthrough_detection():
    assert is_commit_sha(COMMIT_SHA)
    assert not is_commit_sha("main")
    assert not is_commit_sha(COMMIT_SHA[:-1] + "Z")


@pytest.mark.parametrize("ref", ["main", "feature/x-1", "v1.2.3"])
def test_validate_ref_accepts_normal_refs(ref):
    assert validate_ref(ref) == ref


@pytest.mark.parametrize("ref", [
    "", "main..evil", "HEAD~", "../escape", "a\x00b", "a b", "lead/", "/lead",
    "x" * 256,
])
def test_validate_ref_rejects_unsafe_refs(ref):
    with pytest.raises(ValueError):
        validate_ref(ref)


def test_pattern_validation_rejects_absolute_and_traversal():
    with pytest.raises(ValueError):
        validate_patterns(["/abs/path"], "include")
    with pytest.raises(ValueError):
        validate_patterns(["docs/../*"], "exclude")
    with pytest.raises(ValueError):
        validate_patterns(["ok"] * 65, "include")
    assert validate_patterns(["docs/*.md"], "include") == ["docs/*.md"]


def test_resolve_repository_validates_normally():
    target = resolve_repository(
        "https://github.com/ok-org/ok-repo", "main", include=["docs/*"], exclude=["src/*"]
    )
    assert (target.owner, target.repo, target.ref) == ("ok-org", "ok-repo", "main")


def test_resolve_repository_rejects_bad_url_and_ref():
    with pytest.raises(ValueError):
        resolve_repository("https://gitlab.com/ok-org/ok-repo", None)
    with pytest.raises(ValueError):
        resolve_repository("https://github.com/ok-org/ok-repo", "main..evil")


# ---------------------------------------------------------------------------
# File policy
# ---------------------------------------------------------------------------

def test_filter_tree_allowlist_and_exclusions_use_repo_names():
    outcome = filter_tree(_tree_entries())
    assert [f.path for f in outcome.included] == ["README.md", "docs/guide.md", "src/main.py"]
    reasons = dict(outcome.excluded)
    assert reasons["node_modules/react/index.js"] == "generated_or_vendor"
    # dist/ is excluded by directory name (generated_or_vendor wins the check).
    assert reasons["dist/bundle.min.js"] == "generated_or_vendor"
    assert reasons["package-lock.json"] == "lockfile"
    assert reasons[".env"] == "secret_like"
    assert reasons["server.key"] == "secret_like"
    assert reasons["logo.png"] == "unsupported_format"
    assert reasons["design/mockup.psd"] == "unsupported_format"
    assert reasons["src"] == "not_a_file"
    assert outcome.total_bytes == 2231 + 1245 + 828


def test_filter_tree_minified_bundles_outside_generic_dirs():
    entries = [entry("assets/app.min.js", 10, "sha-min"), entry("src/app.js", 10, "sha-ok")]
    outcome = filter_tree(entries)
    assert dict(outcome.excluded)["assets/app.min.js"] == "minified_bundle"
    assert [f.path for f in outcome.included] == ["src/app.js"]


def test_filter_tree_excludes_oversized_files():
    entries = [entry("docs/big.md", 3 * 1024 * 1024, "sha-big"), entry("README.md", 10, README_SHA)]
    outcome = filter_tree(entries, max_file_bytes=2 * 1024 * 1024)
    assert dict(outcome.excluded)["docs/big.md"] == "oversized_file"
    assert [f.path for f in outcome.included] == ["README.md"]


def test_filter_tree_enforces_count_and_total_limits():
    entries = [entry(f"src/f{i}.py", 10, f"sha{i}") for i in range(5)]
    with pytest.raises(RepoLimitError):
        filter_tree(entries, max_files=2)
    with pytest.raises(RepoLimitError):
        filter_tree(entries, max_total_bytes=40)
    outcome = filter_tree(entries, max_files=5, max_total_bytes=100)
    assert len(outcome.included) == 5


def test_filter_tree_include_exclude_globs():
    entries = [
        entry("docs/guide.md", 10, "sha-1"),
        entry("docs/deep/nested.md", 10, "sha-2"),
        entry("src/main.py", 10, "sha-3"),
    ]
    outcome = filter_tree(entries, include=["docs/*"])
    assert [f.path for f in outcome.included] == ["docs/guide.md", "docs/deep/nested.md"]
    assert dict(outcome.excluded)["src/main.py"] == "not_matched_by_include"

    outcome = filter_tree(entries, exclude=["src/*"])
    assert dict(outcome.excluded)["src/main.py"] == "matched_by_exclude"
    assert [f.path for f in outcome.included] == ["docs/guide.md", "docs/deep/nested.md"]


def test_file_decision_file_type_from_extension():
    outcome = filter_tree(_tree_entries())
    types = {f.path: f.file_type for f in outcome.included}
    assert types["README.md"] == "text/markdown"
    assert types["src/main.py"] == "text/plain"


def test_secret_like_name_variants():
    for path in [".env", ".env.production", "id_rsa", "keys/api.pem", "creds/server.key", "secrets.yaml"]:
        assert gh_filters._is_secret_like_name(path.lower()), path
    for path in ["key_format.c", "public_key_display.c", "api.java", "docs/token_use.md"]:
        assert not gh_filters._is_secret_like_name(path.lower()), path


def test_content_secret_scan_flags_high_precision_patterns():
    assert gh_filters.content_secret_scan(
        b"-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n"
    ) is not None
    assert gh_filters.content_secret_scan(b"aws id AKIAIOSFODNN7EXAMPLE for ci") is not None
    assert gh_filters.content_secret_scan(b"token: ghp_" + b"1A2b3C4d5E6f7G8h9I0jK1lM2nO3" * 2) is not None
    assert gh_filters.content_secret_scan(b"plain source code, no secrets here") is None


def test_binary_content_rejected_by_nul_bytes():
    assert gh_filters.looks_binary_content(b"ok\x00binary")
    assert not gh_filters.looks_binary_content(b"plain text")


def test_blob_sha256_is_deterministic():
    assert gh_filters.blob_sha256(b"same") == gh_filters.blob_sha256(b"same")
    assert gh_filters.blob_sha256(b"same") != gh_filters.blob_sha256(b"other")


# ---------------------------------------------------------------------------
# HTTP client over fixtures
# ---------------------------------------------------------------------------

def _fixture_transport(blobs: dict[str, bytes] | None = None, tree: str = "tree.json") -> httpx.MockTransport:
    blobs = blobs or {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/ok-org/ok-repo":
            return httpx.Response(200, json=_fixture("repository.json"))
        if path.startswith("/repos/ok-org/ok-repo/commits/"):
            return httpx.Response(200, json=_fixture("commit_main.json"))
        if path.startswith("/repos/ok-org/ok-repo/git/trees/"):
            return httpx.Response(200, json=_fixture(tree))
        if path.startswith("/repos/ok-org/ok-repo/git/blobs/"):
            sha = path.rsplit("/", 1)[-1]
            if sha in blobs:
                return httpx.Response(200, json=_blob_payload(sha, blobs[sha]))
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(404, json={"message": "Not Found"})

    return httpx.MockTransport(handler)


def _fixture_client(blobs: dict[str, bytes] | None = None, tree: str = "tree.json") -> HttpxGitHubClient:
    http = httpx.AsyncClient(
        base_url="https://api.github.com", transport=_fixture_transport(blobs, tree)
    )
    return HttpxGitHubClient(http=http)


async def test_client_resolves_ref_and_passes_through_commit_sha():
    client = _fixture_client()
    assert await client.resolve_ref("ok-org", "ok-repo", "main") == COMMIT_SHA
    assert await client.resolve_ref("ok-org", "ok-repo", COMMIT_SHA) == COMMIT_SHA

    not_found = HttpxGitHubClient(http=httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda req: httpx.Response(404, json={"message": "Not Found"})),
    ))
    with pytest.raises(GitHubNotFoundError):
        await not_found.resolve_ref("ok-org", "ok-repo", "nope")


async def test_client_get_tree_parses_fixture_and_truncated_flag():
    client = _fixture_client()
    entries, truncated = await client.get_tree("ok-org", "ok-repo", COMMIT_SHA)
    assert not truncated
    paths = [e.path for e in entries]
    assert "docs/guide.md" in paths and "node_modules/react/index.js" in paths
    readme = [e for e in entries if e.path == "README.md"][0]
    assert readme.is_file and readme.size == 2231

    truncated_client = _fixture_client(tree="tree_truncated.json")
    entries, truncated = await truncated_client.get_tree("ok-org", "ok-repo", COMMIT_SHA)
    assert truncated
    assert [e.path for e in entries] == ["README.md", "docs/missing_entries_because_of_truncation.log"]


async def test_client_get_blob_decodes_fixture_base64():
    content = b"print('from fixture')\n"
    client = _fixture_client(blobs={MAIN_PY_SHA: content})
    assert await client.get_blob("ok-org", "ok-repo", MAIN_PY_SHA) == content
    with pytest.raises(GitHubNotFoundError):
        await client.get_blob("ok-org", "ok-repo", "1" * 40)


async def test_client_blocks_redirects_and_maps_status_codes():
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://evil.example.com/x"})

    redirecting = HttpxGitHubClient(http=httpx.AsyncClient(
        base_url="https://api.github.com", transport=httpx.MockTransport(respond)
    ))
    with pytest.raises(GitHubRedirectBlocked):
        await redirecting.get_repository("ok-org", "ok-repo")

    for status, expected in [(401, GitHubAuthError), (403, GitHubRateLimitError), (500, GitHubUnavailableError)]:
        client = HttpxGitHubClient(http=httpx.AsyncClient(
            base_url="https://api.github.com",
            transport=httpx.MockTransport(lambda req, s=status: httpx.Response(s, json={})),
        ))
        with pytest.raises(expected):
            await client.get_repository("ok-org", "ok-repo")


def test_base_url_pin_host():
    assert _validate_base_url("https://api.github.com") == "https://api.github.com"
    with pytest.raises(GitHubConfigError):
        _validate_base_url("http://api.github.com")
    with pytest.raises(GitHubConfigError):
        _validate_base_url("https://evil.com")
    with pytest.raises(GitHubConfigError):
        _validate_base_url("https://api.github.com/v3")


def test_blob_fixture_is_committed_and_realistic():
    """The committed blob fixture is a realistic self-contained GitHub payload."""
    blob = _fixture("blob_readme.json")
    assert blob["encoding"] == "base64"
    decoded = base64.b64decode(blob["content"], validate=True)
    assert b"# Sample Knowledge Base Repository" in decoded


# ---------------------------------------------------------------------------
# Service: preview
# ---------------------------------------------------------------------------

class SimpleRepo:
    def __init__(self, owner):
        self.owner = owner
        self.name = "ok-repo"
        self.default_branch = "main"


class FakeClient:
    """Minimal GitHubClient double for service and background-job tests."""

    def __init__(self, commit_sha: str = COMMIT_SHA, entries=None, blobs=None):
        self.commit_sha = commit_sha
        self.entries = entries or []
        self.blobs = dict(blobs or {})
        self.blob_calls: list[str] = []
        self.release: asyncio.Event | None = None

    async def get_repository(self, owner, repo):
        return SimpleRepo(owner)

    async def resolve_ref(self, owner, repo, ref):
        return self.commit_sha

    async def get_tree(self, owner, repo, commit_sha):
        return self.entries, False

    async def get_blob(self, owner, repo, blob_sha):
        self.blob_calls.append(blob_sha)
        if self.release is not None and len(self.blob_calls) == 1:
            # Block only the first fetch — used for deterministic cancellation.
            await asyncio.wait_for(self.release.wait(), timeout=5)
        blob = self.blobs.get(blob_sha)
        if isinstance(blob, Exception):
            raise blob
        return blob


async def test_build_preview_pins_default_branch_when_ref_missing():
    target = ImportTarget(owner="ok-org", repo="ok-repo", ref="", include=[], exclude=[])
    preview = await build_preview(FakeClient(entries=_tree_entries()), target)
    assert preview.ref == "main"
    assert preview.commit_sha == COMMIT_SHA


async def test_build_preview_returns_prefiltered_files():
    target = resolve_repository("https://github.com/ok-org/ok-repo", "main")
    preview = await build_preview(FakeClient(entries=_tree_entries()), target)
    assert preview.ref == "main" and preview.commit_sha == COMMIT_SHA
    assert [f.path for f in preview.files] == ["README.md", "docs/guide.md", "src/main.py"]
    assert preview.total_bytes == 4304
    assert preview.tree_entry_count == len(_tree_entries())
    assert dict(preview.excluded)[".env"] == "secret_like"


async def test_build_preview_rejects_truncated_tree():
    class TruncatedClient(FakeClient):
        async def get_tree(self, owner, repo, commit_sha):
            return _tree_entries(), True

    target = resolve_repository("https://github.com/ok-org/ok-repo", "main")
    with pytest.raises(ImportRejected) as exc:
        await build_preview(TruncatedClient(entries=_tree_entries()), target)
    assert "truncated" in str(exc.value)


async def test_build_preview_enforces_total_byte_limit(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_IMPORT_MAX_TOTAL_BYTES", 15)
    entries = [
        entry("src/a.md", 10, "sha-a"),
        entry("src/b.md", 10, "sha-b"),
    ]
    target = resolve_repository("https://github.com/ok-org/ok-repo", "main")
    with pytest.raises(ImportRejected) as exc:
        await build_preview(FakeClient(entries=entries), target)
    assert "byte" in str(exc.value)


# ---------------------------------------------------------------------------
# Background import job (feeds the normal document pipeline)
# ---------------------------------------------------------------------------

@pytest.fixture
async def job_env(tmp_path, monkeypatch):
    """In-memory DB + offline stubs around the real ingestion pipeline."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(
        "pipelines.ingestion.pipeline.upsert_chunks",
        lambda chunks, project_id, document_id: [
            f"{document_id}_chunk_{c['chunk_index']}" for c in chunks
        ],
    )
    monkeypatch.setattr("pipelines.embeddings.delete_document_chunks", lambda document_id: None)
    monkeypatch.setattr(
        "pipelines.entity_extraction.extract_entities_from_chunks", AsyncMock(return_value=2)
    )
    monkeypatch.setattr("services.webhooks.fire_event", AsyncMock(return_value=None))

    launched: list[tuple] = []

    def _record_start(session_factory_, document_id, content):
        launched.append((session_factory_, document_id, content))

    monkeypatch.setattr("routers.documents.ingestion_tasks._start_ingestion", _record_start)

    yield factory, launched
    await engine.dispose()


async def _await_job(job, timeout: float = 5.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while job.state == "running" and loop.time() < deadline:
        await asyncio.sleep(0.01)
    assert job.state != "running", "import job did not finish in time"


async def test_job_imports_files_with_provenance_via_normal_pipeline(job_env):
    factory, launched = job_env
    from pipelines.ingestion.runner import ingest_document

    readme_content = base64.b64decode(_fixture("blob_readme.json")["content"])
    blobs = {
        README_SHA: readme_content,
        DOCS_SHA: b"# Guide\n\nEntities link to chunks.\n",
        MAIN_PY_SHA: b"print('hello akgb')\n",
    }
    client = FakeClient(entries=_tree_entries(), blobs=blobs)
    project_id = str(uuid.uuid4())
    job = import_jobs.start_import_job(
        factory, client, _preview(filter_tree(_tree_entries())), project_id, str(uuid.uuid4())
    )
    await _await_job(job)

    assert job.state == "completed"
    assert job.processed_files == 3 and job.failed_files == 0 and job.errors == []
    assert set(job.document_ids) == {args[1] for args in launched}
    assert len(launched) == 3

    # Replay the real pipeline body (parse → chunk → embed → extract → persist).
    for session_factory_, document_id, content in launched:
        await ingest_document(session_factory_, document_id, content)

    async with factory() as db:
        docs = (await db.execute(select(Document))).scalars().all()
        assert len(docs) == 3
        by_name = {d.filename: d for d in docs}
        assert set(by_name) == {"README.md", "docs/guide.md", "src/main.py"}
        for doc in docs:
            assert doc.storage_path.startswith(f"github://ok-org/ok-repo@{COMMIT_SHA}/")
            assert doc.status == "processed"

        chunks = (await db.execute(select(DocumentChunk))).scalars().all()
        assert len(chunks) >= 3
        readme_chunks = [c for c in chunks if c.document_id == by_name["README.md"].id]
        assert any("Sample Knowledge Base Repository" in c.text for c in readme_chunks)

        sources = (await db.execute(select(DocumentSource))).scalars().all()
        assert len(sources) == 3
        source_by_doc = {s.document_id: s for s in sources}
        assert set(source_by_doc) == {d.id for d in docs}
        for doc in docs:
            source = source_by_doc[doc.id]
            assert source.source_type == "github"
            assert (source.repo_owner, source.repo_name) == ("ok-org", "ok-repo")
            assert source.commit_sha == COMMIT_SHA
            assert source.file_path == doc.filename
            assert source.blob_sha and len(source.blob_sha) == 40
            assert len(source.content_sha256) == 64
            assert source.line_start == 1 and source.line_end >= 1


async def test_job_records_per_file_error_and_finishes_remaining(job_env):
    factory, launched = job_env
    blobs = {
        README_SHA: base64.b64decode(_fixture("blob_readme.json")["content"]),
        DOCS_SHA: b"# guide\n",
        MAIN_PY_SHA: RuntimeError("blob unavailable"),
    }
    client = FakeClient(entries=_tree_entries(), blobs=blobs)
    job = import_jobs.start_import_job(
        factory, client, _preview(filter_tree(_tree_entries())), str(uuid.uuid4()), str(uuid.uuid4())
    )
    await _await_job(job)

    assert job.state == "completed"
    assert job.processed_files == 2 and job.failed_files == 1
    assert [e["path"] for e in job.errors] == ["src/main.py"]
    assert "blob unavailable" in job.errors[0]["reason"]
    assert len(launched) == 2


async def test_job_rejects_secret_content_and_oversized_blobs(job_env, monkeypatch):
    factory, launched = job_env
    # Build the preview under default tree limits; the fetch-time byte cap is
    # tightened afterwards so the job-level oversized check is what triggers.
    preview = _preview(filter_tree(_tree_entries()))
    monkeypatch.setattr(settings, "GITHUB_IMPORT_MAX_FILE_BYTES", 64)
    secret = b"-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n"
    big = ("# readme\n" + "x" * 500).encode()
    blobs = {
        README_SHA: big,
        DOCS_SHA: secret,
        MAIN_PY_SHA: b"print('ok')\n",
    }
    client = FakeClient(entries=_tree_entries(), blobs=blobs)
    job = import_jobs.start_import_job(
        factory, client, preview, str(uuid.uuid4()), str(uuid.uuid4())
    )
    await _await_job(job)

    reasons = {e["path"]: e["reason"] for e in job.errors}
    assert reasons["README.md"].startswith("exceeds_")
    assert reasons["docs/guide.md"].startswith("secret_like_content")
    assert job.processed_files == 1 and len(launched) == 1


async def test_job_cancellation_between_files(job_env):
    factory, launched = job_env
    entries = [entry("README.md", 10, README_SHA), entry("docs/guide.md", 10, DOCS_SHA)]
    blobs = {README_SHA: b"# readme\n", DOCS_SHA: b"# guide\n"}
    client = FakeClient(entries=entries, blobs=blobs)
    client.release = asyncio.Event()  # first get_blob blocks until released
    job = import_jobs.start_import_job(
        factory, client, _preview(filter_tree(entries)), str(uuid.uuid4()), str(uuid.uuid4())
    )

    for _ in range(500):
        if client.blob_calls:
            break
        await asyncio.sleep(0.01)
    assert client.blob_calls == [README_SHA]
    assert import_jobs.request_cancel(job.job_id) is True
    client.release.set()
    await _await_job(job)

    # The in-flight file finished; the remaining file was skipped.
    assert job.state == "cancelled"
    assert job.processed_files == 1 and job.failed_files == 0
    assert len(launched) == 1 and job.document_ids == [launched[0][1]]
    assert client.blob_calls.count(DOCS_SHA) == 0

    assert import_jobs.request_cancel(job.job_id) is False
    assert import_jobs.request_cancel(str(uuid.uuid4())) is False


# ---------------------------------------------------------------------------
# HTTP endpoints (offline, with overridden auth/project dependencies)
# ---------------------------------------------------------------------------

class SimpleNamespaceUser:
    def __init__(self, id: str):
        self.id = id


@pytest.fixture
def github_app():
    from core.errors import AppError, app_error_handler
    from core.rate_limit import limiter
    from routers import github as github_router

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.state.limiter = limiter
    app.include_router(github_router.router, prefix="/github")

    project_id = str(uuid.uuid4())
    app.dependency_overrides[github_router.get_project_id] = lambda: project_id
    app.dependency_overrides[github_router.get_current_user] = lambda: SimpleNamespaceUser(
        id=str(uuid.uuid4())
    )
    # No endpoint under test reads data through the request session; import
    # tests stub the audit writer, so a lightweight awaitable stand-in is safe.
    app.dependency_overrides[github_router.get_db] = lambda: AsyncMock(spec=AsyncSession)
    return app, github_router, project_id


def _asgi(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_preview_endpoint_lists_files_with_pinned_commit(github_app, monkeypatch):
    app, github_router, _ = github_app
    monkeypatch.setattr(github_router, "_client_factory", lambda: _fixture_client())
    async with _asgi(app) as http:
        response = await http.post(
            "/github/import/preview",
            json={"repo_url": "https://github.com/ok-org/ok-repo", "ref": "main"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["owner"] == "ok-org" and payload["repo"] == "ok-repo"
    assert payload["ref"] == "main" and payload["commit_sha"] == COMMIT_SHA
    assert payload["included_files"] == 3
    assert payload["total_bytes"] == 4304
    assert {f["path"] for f in payload["files"]} == {
        "README.md", "docs/guide.md", "src/main.py",
    }
    reasons = {e["path"]: e["reason"] for e in payload["excluded"]}
    assert reasons[".env"] == "secret_like"
    assert reasons["package-lock.json"] == "lockfile"


async def test_preview_endpoint_blocks_cross_host_redirect(github_app, monkeypatch):
    app, github_router, _ = github_app

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://evil.example.com/x"})

    client = HttpxGitHubClient(http=httpx.AsyncClient(
        base_url="https://api.github.com", transport=httpx.MockTransport(respond)
    ))
    monkeypatch.setattr(github_router, "_client_factory", lambda: client)
    async with _asgi(app) as http:
        response = await http.post(
            "/github/import/preview",
            json={"repo_url": "https://github.com/ok-org/ok-repo"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "github_import_rejected"


async def test_preview_endpoint_validates_url_and_ref(github_app):
    app, _, _ = github_app
    async with _asgi(app) as http:
        response = await http.post(
            "/github/import/preview",
            json={"repo_url": "https://gitlab.com/ok-org/ok-repo"},
        )
        assert response.status_code == 422
        assert "github.com" in response.json()["error"]["message"]

        response = await http.post(
            "/github/import/preview",
            json={"repo_url": "https://github.com/ok-org/ok-repo", "ref": "../escape"},
        )
        assert response.status_code == 422


@pytest.fixture
async def import_backend(monkeypatch, tmp_path):
    """Offline backend: DB factory + stubbed normal pipeline for endpoint jobs."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # The router resolves the job's session factory by module attribute at call
    # time; request-session consumers are overridden in github_app instead.
    monkeypatch.setattr("db.session.async_session_factory", factory)
    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(
        "pipelines.ingestion.pipeline.upsert_chunks",
        lambda chunks, p, document_id: [f"{document_id}_chunk_{c['chunk_index']}" for c in chunks],
    )
    monkeypatch.setattr("pipelines.embeddings.delete_document_chunks", lambda document_id: None)
    monkeypatch.setattr(
        "pipelines.entity_extraction.extract_entities_from_chunks", AsyncMock(return_value=1)
    )
    monkeypatch.setattr("services.webhooks.fire_event", AsyncMock(return_value=None))
    monkeypatch.setattr("routers.documents.ingestion_tasks._start_ingestion", lambda *args: None)
    return engine


async def test_import_endpoint_starts_job_and_reports_status(github_app, import_backend, monkeypatch):
    engine = import_backend
    app, github_router, _ = github_app
    blobs = {
        README_SHA: base64.b64decode(_fixture("blob_readme.json")["content"]),
        DOCS_SHA: b"# guide\n",
        MAIN_PY_SHA: b"print('hi')\n",
    }
    monkeypatch.setattr(github_router, "write_audit_log", AsyncMock(return_value=None))
    # Hold the first blob fetch so the 202 deterministically reports a running job.
    client = FakeClient(entries=_tree_entries(), blobs=blobs)
    client.release = asyncio.Event()
    monkeypatch.setattr(github_router, "_client_factory", lambda: client)

    job_id = None
    job = None
    try:
        async with _asgi(app) as http:
            response = await http.post(
                "/github/import/repository",
                json={"repo_url": "https://github.com/ok-org/ok-repo", "ref": "main"},
            )
            assert response.status_code == 202, response.text
            started = response.json()
            assert started["state"] == "running"
            assert started["commit_sha"] == COMMIT_SHA
            assert started["total_files"] == 3
            job_id = started["job_id"]
            job = import_jobs.get_job(job_id)
            assert job is not None

        client.release.set()
        await _await_job(job)
        assert job.state == "completed" and job.processed_files == 3

        async with _asgi(app) as http:
            status = await http.get(f"/github/import/{job_id}")
            assert status.status_code == 200
            snapshot = status.json()
            assert snapshot["state"] == "completed"
            assert snapshot["progress"] == 1.0
            assert snapshot["failed_files"] == 0
            assert snapshot["commit_sha"] == COMMIT_SHA
            assert snapshot["repository"] == "ok-org/ok-repo"

            cancel = await http.post(f"/github/import/{job_id}/cancel")
            assert cancel.status_code == 200
            assert cancel.json()["cancel_requested"] is False  # already finished

            unknown = await http.get(f"/github/import/{uuid.uuid4()}")
            assert unknown.status_code == 404
    finally:
        if job_id:
            import_jobs._jobs.pop(job_id, None)
        await engine.dispose()


async def test_job_status_and_cancel_are_project_scoped(github_app):
    app, _, owner_project = github_app
    other_job = import_jobs.ImportJobState(
        job_id=str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        owner="ok-org",
        repo="ok-repo",
        ref="main",
        commit_sha=COMMIT_SHA,
    )
    owned_job = import_jobs.ImportJobState(
        job_id=str(uuid.uuid4()),
        project_id=owner_project,
        owner="ok-org",
        repo="ok-repo",
        ref="main",
        commit_sha=COMMIT_SHA,
    )
    import_jobs._jobs[other_job.job_id] = other_job
    import_jobs._jobs[owned_job.job_id] = owned_job
    try:
        async with _asgi(app) as http:
            foreign = await http.get(f"/github/import/{other_job.job_id}")
            assert foreign.status_code == 404

            visible = await http.get(f"/github/import/{owned_job.job_id}")
            assert visible.status_code == 200
            assert visible.json()["state"] == "running"

            cancel_response = await http.post(f"/github/import/{owned_job.job_id}/cancel")
            assert cancel_response.json()["cancel_requested"] is True
    finally:
        import_jobs._jobs.pop(other_job.job_id, None)
        import_jobs._jobs.pop(owned_job.job_id, None)


async def test_import_endpoint_refuses_when_no_files_match(github_app, monkeypatch):
    app, github_router, _ = github_app
    filtered = [
        e for e in _tree_entries()
        if e.path not in ("README.md", "docs/guide.md", "src/main.py")
    ]
    monkeypatch.setattr(github_router, "_client_factory", lambda: FakeClient(entries=filtered))
    async with _asgi(app) as http:
        response = await http.post(
            "/github/import/repository",
            json={"repo_url": "https://github.com/ok-org/ok-repo", "ref": "main"},
        )
    assert response.status_code == 422
    assert "No files match" in response.json()["error"]["message"]


async def test_import_endpoint_refuses_limit_violations(github_app, monkeypatch):
    app, github_router, _ = github_app
    monkeypatch.setattr(settings, "GITHUB_IMPORT_MAX_TOTAL_BYTES", 1000)
    monkeypatch.setattr(github_router, "_client_factory", lambda: FakeClient(entries=_tree_entries()))
    async with _asgi(app) as http:
        response = await http.post(
            "/github/import/repository",
            json={"repo_url": "https://github.com/ok-org/ok-repo", "ref": "main"},
        )
    assert response.status_code == 422
    assert "byte" in response.json()["error"]["message"]
