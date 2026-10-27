"""Background GitHub import jobs — progress, per-file errors, cancellation.

Conventions follow the rest of the codebase:
- Strong asyncio.Task references (no garbage-collected mid-run tasks).
- The job opens its own session via ``async_session_factory`` (request
  sessions die with the response).
- Each file flows through the normal document pipeline: it becomes a regular
  ``documents`` row, its bytes are saved as a durable original, and
  the job awaits parse → chunk → embed → extract per file.
- Repository text is untrusted retrieval content: it is never executed, and
  secret-looking content is refused before anything is stored.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.config import settings
from core.security import User
from db.models import Document, DocumentSource
from pipelines.ingestion.runner import ingest_document
from services.documents import upload_document
from services.documents.storage import save_original, delete_original

from .client import GitHubClient
from .filters import (
    FileDecision,
    blob_sha256,
    content_secret_scan,
    looks_binary_content,
)
from .service import ImportRejected, PreviewResult

logger = logging.getLogger(__name__)

MAX_TRACKED_JOBS = 100
MAX_RECORDED_ERRORS = 200


@dataclass
class ImportJobState:
    job_id: str
    project_id: str
    owner: str
    repo: str
    ref: str
    commit_sha: str
    state: str = "running"  # running | completed | cancelled | failed
    message: str = ""
    cancel_requested: bool = False
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    errors: list[dict] = field(default_factory=list)
    document_ids: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: str | None = None

    @property
    def progress(self) -> float:
        if not self.total_files:
            return 0.0
        return round((self.processed_files + self.failed_files) / self.total_files, 4)

    def snapshot(self) -> dict:
        return {
            "job_id": self.job_id,
            "state": self.state,
            "message": self.message,
            "cancel_requested": self.cancel_requested,
            "owner": self.owner,
            "repository": f"{self.owner}/{self.repo}",
            "ref": self.ref,
            "commit_sha": self.commit_sha,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "progress": self.progress,
            "errors": self.errors,
            "document_ids": self.document_ids,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


# Registry keyed by job id. Task objects are kept in a module-level set so the
# event loop never collects a running job (same pattern as core.task_queue).
_jobs: dict[str, ImportJobState] = {}
_running_tasks: set[asyncio.Task] = set()
# The specific client used per job; also lets tests swap in fakes.
_job_clients: dict[str, GitHubClient] = {}


def get_job(job_id: str) -> ImportJobState | None:
    return _jobs.get(job_id)


def request_cancel(job_id: str) -> bool:
    """Mark a running job for cancellation between files."""
    job = _jobs.get(job_id)
    if job is None or job.state != "running":
        return False
    job.cancel_requested = True
    return True


def _remember_job(job: ImportJobState) -> None:
    while len(_jobs) >= MAX_TRACKED_JOBS:
        oldest_finished = next((key for key, value in _jobs.items() if value.state != "running"), None)
        if oldest_finished is None:
            raise ImportRejected("Too many running imports; wait for a job to finish")
        _jobs.pop(oldest_finished)
    _jobs[job.job_id] = job


def start_import_job(
    session_factory,
    client: GitHubClient,
    preview: PreviewResult,
    project_id: str,
    user_id: str,
) -> ImportJobState:
    """Spawn the background import; returns the job record immediately."""
    job = ImportJobState(
        job_id=str(uuid.uuid4()),
        project_id=project_id,
        owner=preview.owner,
        repo=preview.repo,
        ref=preview.ref,
        commit_sha=preview.commit_sha,
        total_files=len(preview.files),
    )
    _remember_job(job)
    _job_clients[job.job_id] = client
    task = asyncio.create_task(
        _run_import(
            session_factory,
            client,
            preview,
            job,
            project_id,
            user_id,
        ),
        name=f"github-import-{job.job_id}",
    )
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return job


async def _run_import(
    session_factory,
    client: GitHubClient,
    preview: PreviewResult,
    job: ImportJobState,
    project_id: str,
    user_id: str,
):
    try:
        for decision in preview.files:
            if job.cancel_requested and job.state == "running":
                job.state = "cancelled"
                job.message = "Cancelled before all files were processed"
                break
            try:
                document_id = await _ingest_file(
                    session_factory, client, job, decision, project_id, user_id
                )
                if document_id:
                    job.processed_files += 1
                    if len(job.document_ids) < 500:
                        job.document_ids.append(document_id)
                else:
                    job.failed_files += 1
            except Exception as exc:
                job.failed_files += 1
                _record_error(job, decision.path, f"{type(exc).__name__}: {exc}")
                logger.warning(
                    "GitHub import file failed: %s/%s %s (%s)",
                    preview.owner, preview.repo, decision.path, type(exc).__name__,
                )
        else:
            if job.state == "running":
                job.state = "completed"
                suffix = f" ({job.failed_files} failed)" if job.failed_files else ""
                job.message = f"Imported {job.processed_files} file(s){suffix}"
    except Exception as exc:
        job.state = "failed"
        job.message = f"Import failed: {type(exc).__name__}"
        logger.exception("GitHub import job crashed (job_id=%s)", job.job_id)
    finally:
        job.finished_at = datetime.now(timezone.utc).isoformat()
        _job_clients.pop(job.job_id, None)
        close = getattr(client, "aclose", None)
        if close is not None:
            # Jobs own their client; the injected test clients may not close.
            try:
                await close()
            except Exception:
                logger.exception("GitHub client close failed")


def _record_error(job: ImportJobState, path: str, reason: str) -> None:
    if len(job.errors) < MAX_RECORDED_ERRORS:
        job.errors.append({"path": path[:1024], "reason": reason[:500]})


async def _ingest_file(
    session_factory,
    client: GitHubClient,
    job: ImportJobState,
    decision: FileDecision,
    project_id: str,
    user_id: str,
) -> str:
    """Fetch one file and run it through the normal document pipeline."""
    blob = await client.get_blob(job.owner, job.repo, decision.sha)
    max_file_bytes = settings.GITHUB_IMPORT_MAX_FILE_BYTES
    if len(blob) > max_file_bytes:
        _record_error(job, decision.path, f"exceeds_{max_file_bytes}_bytes")
        return ""
    if looks_binary_content(blob):
        _record_error(job, decision.path, "binary_content")
        return ""
    secret_reason = content_secret_scan(blob)
    if secret_reason:
        # Never log or store the matched content — just the pattern kind.
        _record_error(job, decision.path, f"secret_like_content: {secret_reason}")
        return ""

    content_hash = blob_sha256(blob)
    document_id = str(uuid.uuid4())
    filename = decision.path  # repo-relative path; citations show it verbatim
    storage_uri = f"github://{job.owner}/{job.repo}@{job.commit_sha}/{decision.path}"
    created = await _persist_document(
        session_factory, job, decision, project_id, user_id,
        document_id, filename, storage_uri, content_hash, blob,
    )
    # One pipeline per job at a time. Completion means searchable evidence,
    # rather than merely launching a detached task with unobserved failures.
    await ingest_document(session_factory, created, bytes(blob))
    async with session_factory() as db:
        document = await db.get(Document, uuid.UUID(created))
        if document is None or document.status != "processed":
            _record_error(job, decision.path, "document_ingestion_failed; inspect document status")
            return ""
    return created


async def _persist_document(
    session_factory,
    job: ImportJobState,
    decision: FileDecision,
    project_id: str,
    user_id: str,
    document_id: str,
    filename: str,
    storage_uri: str,
    content_hash: str,
    blob: bytes,
) -> str:
    """Insert document + provenance and save the original atomically."""
    line_count = blob.count(b"\n") + (0 if blob.endswith(b"\n") else 1) if blob else 0
    async with session_factory() as db:
        doc = await upload_document(
            db=db,
            user=User(id=user_id, email=None),
            filename=filename,
            file_type=decision.file_type,
            storage_path=storage_uri,
            project_id=project_id,
            document_id=document_id,
        )
        db.add(
            DocumentSource(
                document_id=uuid.UUID(document_id),
                project_id=uuid.UUID(project_id),
                source_type="github",
                repo_owner=job.owner,
                repo_name=job.repo,
                commit_sha=job.commit_sha,
                file_path=decision.path,
                blob_sha=decision.sha,
                content_sha256=content_hash,
                line_start=1,
                line_end=line_count or None,
            )
        )
        try:
            await db.flush()
            await asyncio.to_thread(save_original, project_id, document_id, bytes(blob))
            await db.commit()
        except Exception:
            await db.rollback()
            try:
                await asyncio.to_thread(delete_original, project_id, document_id)
            except Exception:
                logger.exception("Original cleanup failed after persistence error")
            raise

    return doc["id"]
