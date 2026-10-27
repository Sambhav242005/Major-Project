"""GitHub import orchestration — resolution and preview (no side effects)."""

from dataclasses import dataclass, field

from .client import (
    GitHubClient,
    GitHubError,
    RepositoryInfo,
)
from .filters import (
    FileDecision,
    FilterOutcome,
    is_commit_sha,
    parse_repo_url,
    validate_patterns,
    validate_ref,
)


@dataclass(frozen=True)
class ImportTarget:
    owner: str
    repo: str
    ref: str  # validated ref as supplied ("" when only the default branch is used)
    include: list[str]
    exclude: list[str]


@dataclass(frozen=True)
class ResolvedRepository:
    owner: str
    repo: str
    ref: str
    commit_sha: str
    repo_info: RepositoryInfo


@dataclass
class PreviewResult:
    owner: str
    repo: str
    ref: str
    commit_sha: str
    files: list[FileDecision] = field(default_factory=list)
    excluded: list[tuple[str, str]] = field(default_factory=list)
    total_bytes: int = 0
    tree_entry_count: int = 0
    tree_truncated: bool = False


class ImportRejected(ValueError):
    """The request or repository cannot be imported; safe client-facing reason."""


def resolve_repository(
    repo_url: str,
    ref: str | None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> ImportTarget:
    """Parse and validate the request shape (no network calls)."""
    owner, repo = parse_repo_url(repo_url)
    include_validated = validate_patterns(include, "include")
    exclude_validated = validate_patterns(exclude, "exclude")
    ref_validated = validate_ref(ref) if ref not in (None, "") else ""
    return ImportTarget(
        owner=owner,
        repo=repo,
        ref=ref_validated,
        include=include_validated,
        exclude=exclude_validated,
    )


async def build_preview(
    client: GitHubClient,
    target: ImportTarget,
) -> PreviewResult:
    """Resolve the ref to a commit SHA and apply policy to the tree.

    Fetches repository metadata, the pinned commit and the (recursive) tree —
    no file contents are downloaded during a preview.
    """
    from .filters import filter_tree

    if not (target.ref and is_commit_sha(target.ref)):
        repo_info = await client.get_repository(target.owner, target.repo)
        ref = target.ref or repo_info.default_branch
        ref = validate_ref(ref)
        commit_sha = await client.resolve_ref(target.owner, target.repo, ref)
    else:
        ref = target.ref
        commit_sha = target.ref.lower()

    try:
        entries, truncated = await client.get_tree(target.owner, target.repo, commit_sha)
    except GitHubError as exc:
        raise ImportRejected(str(exc)) from exc

    if truncated:
        raise ImportRejected(
            "GitHub truncated the repository tree; this repository is too large to import wholesale"
        )

    try:
        outcome: FilterOutcome = filter_tree(
            entries,
            include=target.include,
            exclude=target.exclude,
        )
    except Exception as exc:  # RepoLimitError and policy violations
        raise ImportRejected(str(exc)) from exc

    return PreviewResult(
        owner=target.owner,
        repo=target.repo,
        ref=ref,
        commit_sha=commit_sha,
        files=outcome.included,
        excluded=outcome.excluded,
        total_bytes=outcome.total_bytes,
        tree_entry_count=len(entries),
        tree_truncated=truncated,
    )


def default_client() -> GitHubClient:
    """Create the production client; tests inject their own implementations."""
    from .client import HttpxGitHubClient

    return HttpxGitHubClient()
