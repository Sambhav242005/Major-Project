"""GitHub repository import (Phase 1: public repositories).

Feature package: client abstraction, offline-testable policy, request
orchestration and background import jobs.
"""
from .client import (
    GitHubAuthError,
    GitHubClient,
    GitHubConfigError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRedirectBlocked,
    GitHubUnavailableError,
)
from .filters import (
    FileDecision,
    FilterOutcome,
    RepoLimitError,
    filter_tree,
    is_commit_sha,
    parse_repo_url,
    validate_patterns,
    validate_ref,
)
from .service import (
    ImportRejected,
    ImportTarget,
    PreviewResult,
    build_preview,
    default_client,
    resolve_repository,
)

__all__ = [
    "FileDecision",
    "FilterOutcome",
    "GitHubAuthError",
    "GitHubClient",
    "GitHubConfigError",
    "GitHubError",
    "GitHubNotFoundError",
    "GitHubRateLimitError",
    "GitHubRedirectBlocked",
    "GitHubUnavailableError",
    "ImportRejected",
    "ImportTarget",
    "PreviewResult",
    "RepoLimitError",
    "build_preview",
    "default_client",
    "filter_tree",
    "is_commit_sha",
    "parse_repo_url",
    "resolve_repository",
    "validate_patterns",
    "validate_ref",
]
