"""GitHub repository ingestion endpoints (Phase 1: public repositories).

Thin HTTP surface over ``services/github_import``:

- ``POST /github/import/preview`` — resolve ref → file list + bytes (no import).
- ``POST /github/import/repository`` — start a background import job (202).
- ``GET  /github/import/{job_id}`` — progress, per-file errors, state.
- ``POST /github/import/{job_id}/cancel`` — request cancellation.

Project membership is enforced via ``core.deps.get_project_id``; imported
repository text is untrusted retrieval content and is never executed.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.errors import AppError
from core.rate_limit import limiter
from core.security import User, get_current_user
from db.session import get_db
from schemas.github import (
    GitHubCancelResponse,
    GitHubImportJobResponse,
    GitHubImportResponse,
    GitHubPreviewExclusion,
    GitHubPreviewFile,
    GitHubPreviewResponse,
    GitHubRepoPreviewRequest,
)
from services.audit import write_audit_log
from services.github_import import (
    ImportRejected,
    build_preview,
    default_client,
    resolve_repository,
)
from services.github_import import jobs as import_jobs

router = APIRouter()
logger = logging.getLogger(__name__)

# Client factory indirection — tests swap this for fixture-backed fakes so the
# suite stays fully offline. Production always uses api.github.com.
_client_factory = default_client


class GitHubImportBlocked(AppError):
    """Repository or request rejected by import policy (client-facing)."""

    status_code = 422
    error_code = "github_import_rejected"


def _from_rejection(exc: Exception) -> GitHubImportBlocked:
    from services.github_import.client import GitHubError

    if isinstance(exc, (ImportRejected, ValueError, GitHubError)):
        # These carry only safe, client-facing reasons — never repo content.
        return GitHubImportBlocked(str(exc))
    return GitHubImportBlocked("Repository preview failed")


@router.post("/import/preview", response_model=GitHubPreviewResponse)
@limiter.limit("10/minute")
async def preview_repository(
    request: Request,
    response: Response,
    payload: GitHubRepoPreviewRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolve the ref to a commit SHA and list the files that would import."""
    try:
        target = resolve_repository(
            payload.repo_url,
            payload.ref,
            payload.include,
            payload.exclude,
        )
        client = _client_factory()
        preview = await build_preview(client, target)
    except ImportRejected as exc:
        raise _from_rejection(exc) from None
    except Exception as exc:
        raise _from_rejection(exc) from exc
    return GitHubPreviewResponse(
        owner=preview.owner,
        repo=preview.repo,
        ref=preview.ref,
        commit_sha=preview.commit_sha,
        files=[
            GitHubPreviewFile(path=f.path, size=f.size, blob_sha=f.sha, file_type=f.file_type)
            for f in preview.files
        ],
        excluded=[
            GitHubPreviewExclusion(path=path, reason=reason)
            for path, reason in preview.excluded
        ],
        included_files=len(preview.files),
        excluded_files=len(preview.excluded),
        total_bytes=preview.total_bytes,
        tree_entry_count=preview.tree_entry_count,
    )


@router.post("/import/repository", response_model=GitHubImportResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def import_repository(
    request: Request,
    response: Response,
    payload: GitHubRepoPreviewRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pin the ref, then import the allowed files in a background job.

    Each file is imported through the normal document pipeline (documents row →
    saved original → parse/chunk/embed/extract), with provenance retained.
    """
    from db.session import async_session_factory

    try:
        target = resolve_repository(
            payload.repo_url,
            payload.ref,
            payload.include,
            payload.exclude,
        )
        client = _client_factory()
        preview = await build_preview(client, target)
    except ImportRejected as exc:
        raise _from_rejection(exc) from None
    except Exception as exc:
        raise _from_rejection(exc) from exc

    if not preview.files:
        raise GitHubImportBlocked("No files match the import policy")

    job = import_jobs.start_import_job(
        async_session_factory, client, preview, project_id, user.id
    )
    try:
        await write_audit_log(
            db=db,
            project_id=project_id,
            actor_id=user.id,
            action="github_import.started",
            resource_type="github_import",
            resource_id=job.job_id,
            meta={
                "repository": f"{preview.owner}/{preview.repo}",
                "ref": preview.ref,
                "commit_sha": preview.commit_sha,
                "files": job.total_files,
            },
        )
        await db.commit()
    except Exception:
        logger.exception("Audit write failed for github_import.started")
        await db.rollback()
    return GitHubImportResponse(
        state=job.state,
        job_id=job.job_id,
        owner=preview.owner,
        repo=preview.repo,
        ref=preview.ref,
        commit_sha=preview.commit_sha,
        total_files=job.total_files,
        message=job.message,
    )


def _job_or_404(job_id: str) -> "import_jobs.ImportJobState":
    job = import_jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


@router.get("/import/{job_id}", response_model=GitHubImportJobResponse)
async def get_import_job(
    job_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = _job_or_404(job_id)
    if job.project_id != project_id:
        # Treat other projects' jobs as unknown.
        raise HTTPException(status_code=404, detail="Import job not found")
    return GitHubImportJobResponse(**job.snapshot())


@router.post("/import/{job_id}/cancel", response_model=GitHubCancelResponse)
async def cancel_import_job(
    job_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = _job_or_404(job_id)
    if job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Import job not found")
    requested = import_jobs.request_cancel(job_id)
    return GitHubCancelResponse(job_id=job_id, cancel_requested=requested)
