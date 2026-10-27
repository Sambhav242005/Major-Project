"""GitHub API client behind an abstract interface.

The rest of the feature depends only on the ``GitHubClient`` protocol, so unit
tests construct clients over local fixture payloads and the live implementation
stays a thin, narrow wrapper around api.github.com. The suite never touches the
network: tests inject an ``httpx.MockTransport``.

Security posture:
- Only https://api.github.com is accepted as the API host.
- Redirects are never followed; this blocks cross-host redirects outright.
- Response bodies are size-capped before JSON parsing.
"""

import base64
import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from core.config import settings
from .filters import ALLOWED_API_HOST, is_commit_sha, validate_ref

# Cap raw response bytes before json.loads to bound memory usage.
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class GitHubError(Exception):
    """Base class: message is safe to surface; never includes repo content."""


class GitHubConfigError(GitHubError):
    """The configured API base URL/host is not allowed."""


class GitHubAuthError(GitHubError):
    """GitHub rejected credentials (401) or authorized them away."""


class GitHubNotFoundError(GitHubError):
    """Repository, ref or blob does not exist (or is private)."""


class GitHubRateLimitError(GitHubError):
    """GitHub rate limit / abuse detection (403)."""


class GitHubUnavailableError(GitHubError):
    """GitHub is having trouble (5xx) or returned an unusable payload."""


class GitHubRedirectBlocked(GitHubError):
    """GitHub responded with a redirect; following it is not allowed."""


@dataclass(frozen=True)
class TreeEntry:
    path: str
    type: str  # "blob" or "tree"
    sha: str
    size: int | None  # blobs report size; trees do not

    @property
    def is_file(self) -> bool:
        return self.type == "blob"


@dataclass(frozen=True)
class RepositoryInfo:
    owner: str
    name: str
    default_branch: str


class GitHubClient(Protocol):
    """Everything the import service may do against a repository."""

    async def get_repository(self, owner: str, repo: str) -> RepositoryInfo: ...

    async def resolve_ref(self, owner: str, repo: str, ref: str) -> str: ...

    async def get_tree(self, owner: str, repo: str, commit_sha: str) -> tuple[list[TreeEntry], bool]: ...

    async def get_blob(self, owner: str, repo: str, blob_sha: str) -> bytes: ...


def _json_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "akgb-knowledge-base-importer",
    }


def _validate_base_url(base_url: str) -> str:
    parsed = httpx.URL(base_url)
    if parsed.scheme != "https" or parsed.path.rstrip("/") not in ("", "/"):
        raise GitHubConfigError("GITHUB_API_BASE_URL must be a bare HTTPS origin")
    if (parsed.host or "").lower() != ALLOWED_API_HOST:
        raise GitHubConfigError(
            f"GITHUB_API_BASE_URL host must be {ALLOWED_API_HOST}"
        )
    return base_url.rstrip("/")


def _parse_repository(payload: dict) -> RepositoryInfo:
    try:
        owner = payload["owner"]["login"]
        name = payload["name"]
        branch = payload["default_branch"]
    except (KeyError, TypeError) as exc:
        raise GitHubUnavailableError("Unexpected repository payload from GitHub") from exc
    if not isinstance(owner, str) or not isinstance(name, str) or not isinstance(branch, str) or not branch:
        raise GitHubUnavailableError("Unexpected repository payload from GitHub")
    return RepositoryInfo(owner=owner, name=name, default_branch=branch)


def _parse_tree(payload: dict) -> tuple[list[TreeEntry], bool]:
    if not isinstance(payload, dict) or not isinstance(payload.get("tree"), list):
        raise GitHubUnavailableError("Unexpected tree payload from GitHub")
    entries = []
    for item in payload["tree"]:
        if not isinstance(item, dict):
            raise GitHubUnavailableError("Unexpected tree payload from GitHub")
        path, sha = item.get("path"), item.get("sha")
        kind = item.get("type")
        if not isinstance(path, str) or not isinstance(sha, str) or kind not in ("blob", "tree", "commit"):
            raise GitHubUnavailableError("Unexpected tree payload from GitHub")
        size = item.get("size")
        if size is not None and not isinstance(size, int):
            raise GitHubUnavailableError("Unexpected tree payload from GitHub")
        entries.append(TreeEntry(path=path, type=kind, sha=sha, size=size))
    return entries, bool(payload.get("truncated"))


def parse_blob(payload: dict) -> bytes:
    """Decode a git blob payload (base64 content) returned by GitHub."""
    if not isinstance(payload, dict):
        raise GitHubUnavailableError("Unexpected blob payload from GitHub")
    if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        raise GitHubUnavailableError("Unexpected blob payload from GitHub")
    try:
        # GitHub wraps base64 at fixed-width lines, including a final newline.
        return base64.b64decode("".join(payload["content"].split()), validate=True)
    except ValueError as exc:
        raise GitHubUnavailableError("Blob payload is not valid base64") from exc


class HttpxGitHubClient:
    """Default implementation talking to https://api.github.com."""

    def __init__(self, base_url: str | None = None, http: httpx.AsyncClient | None = None):
        self.base_url = _validate_base_url(base_url or settings.GITHUB_API_BASE_URL)
        self._http = http
        if http is not None and _url_host(http.base_url or self.base_url) != ALLOWED_API_HOST:
            # A client provided by tests must still honour the host policy.
            raise GitHubConfigError(f"API host must be {ALLOWED_API_HOST}")

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            # follow_redirects=False keeps cross-host redirects blocked.
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                follow_redirects=False,
                trust_env=False,
                headers=_json_headers(),
                timeout=httpx.Timeout(30.0),
            )
        return self._http

    async def _request_json(self, url_path: str, params: dict | None = None) -> dict:
        client = self._client()
        try:
            async with client.stream("GET", url_path, params=params, headers=_json_headers()) as response:
                if response.is_redirect:
                    raise GitHubRedirectBlocked("GitHub API redirects are not followed")
                if response.status_code == 401:
                    raise GitHubAuthError("GitHub authentication failed; configure a repository token")
                if response.status_code == 404:
                    raise GitHubNotFoundError("Repository, ref or object not found (or private)")
                if response.status_code in (403, 429):
                    raise GitHubRateLimitError("GitHub rate limit reached or access forbidden")
                if response.status_code >= 400:
                    raise GitHubUnavailableError(f"GitHub responded with status {response.status_code}")
                if (response.url.host or "").lower() != ALLOWED_API_HOST:
                    raise GitHubRedirectBlocked("GitHub API responded from an unexpected host")
                content = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise GitHubUnavailableError("GitHub response exceeds the accepted size limit")
                    content.extend(chunk)
        except httpx.HTTPError as exc:
            raise GitHubUnavailableError(f"GitHub request failed: {type(exc).__name__}") from exc
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitHubUnavailableError("GitHub response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise GitHubUnavailableError("GitHub response is not a JSON object")
        return payload

    async def get_repository(self, owner: str, repo: str) -> RepositoryInfo:
        return _parse_repository(await self._request_json(f"/repos/{owner}/{repo}"))

    async def resolve_ref(self, owner: str, repo: str, ref: str) -> str:
        """Pin a branch/tag/SHA ref to the full commit SHA it points at."""
        validate_ref(ref)
        if is_commit_sha(ref):
            return ref.lower()
        payload = await self._request_json(f"/repos/{owner}/{repo}/commits/{ref}", params={"per_page": 1})
        sha = payload.get("sha")
        if not isinstance(sha, str) or not is_commit_sha(sha):
            raise GitHubUnavailableError("GitHub commit payload did not include a commit SHA")
        return sha

    async def get_tree(self, owner: str, repo: str, commit_sha: str) -> tuple[list[TreeEntry], bool]:
        validate_ref(commit_sha)
        payload = await self._request_json(
            f"/repos/{owner}/{repo}/git/trees/{commit_sha}", params={"recursive": "1"}
        )
        return _parse_tree(payload)

    async def get_blob(self, owner: str, repo: str, blob_sha: str) -> bytes:
        validate_ref(blob_sha)
        if not is_commit_sha(blob_sha):
            # Blobs are addressed by SHA too; a 40-hex requirement is met.
            raise GitHubUnavailableError("Blob request requires a SHA")
        return parse_blob(await self._request_json(f"/repos/{owner}/{repo}/git/blobs/{blob_sha}"))

    async def aclose(self) -> None:
        if self._http is not None:
            http_client = self._http
            self._http = None
            await http_client.aclose()


def _url_host(url: str | httpx.URL) -> str | None:
    parsed = url if isinstance(url, httpx.URL) else httpx.URL(str(url))
    return (parsed.host or "").lower()
