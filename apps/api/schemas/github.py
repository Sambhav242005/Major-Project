"""Schemas for GitHub repository ingestion endpoints."""

from pydantic import BaseModel, Field


class GitHubRepoPreviewRequest(BaseModel):
    repo_url: str = Field(..., min_length=1, max_length=4096, description="https://github.com/{owner}/{repo}")
    ref: str | None = Field(None, max_length=255, description="Branch, tag or full commit SHA; defaults to the repository's default branch")
    include: list[str] | None = Field(None, description="Optional repository-relative glob patterns (fnmatch syntax)")
    exclude: list[str] | None = Field(None, description="Optional repository-relative glob patterns to exclude")


class GitHubPreviewFile(BaseModel):
    path: str
    size: int
    blob_sha: str
    file_type: str


class GitHubPreviewExclusion(BaseModel):
    path: str
    reason: str


class GitHubPreviewResponse(BaseModel):
    owner: str
    repo: str
    ref: str
    commit_sha: str
    files: list[GitHubPreviewFile]
    excluded: list[GitHubPreviewExclusion]
    included_files: int
    excluded_files: int
    total_bytes: int
    tree_entry_count: int


class GitHubImportResponse(BaseModel):
    state: str
    job_id: str
    owner: str
    repo: str
    ref: str
    commit_sha: str
    total_files: int
    message: str


class GitHubImportJobResponse(BaseModel):
    job_id: str
    state: str
    message: str
    cancel_requested: bool
    owner: str
    repository: str
    ref: str
    commit_sha: str
    total_files: int
    processed_files: int
    failed_files: int
    progress: float
    errors: list[dict]
    document_ids: list[str]
    created_at: str
    finished_at: str | None


class GitHubCancelResponse(BaseModel):
    job_id: str
    cancel_requested: bool
