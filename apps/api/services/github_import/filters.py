"""GitHub import policy — parsing, validation, allowlists and size limits.

Pure logic with no I/O so every rule can be unit-tested offline. Repository
text is treated as untrusted retrieval content: nothing here executes code,
hooks, installers, or instructions found in imported files.
"""

import base64
import fnmatch
import hashlib
import re
from dataclasses import dataclass, field

from core.config import settings

# ---------------------------------------------------------------------------
# Host validation (Phase 1: github.com / api.github.com only)
# ---------------------------------------------------------------------------

ALLOWED_REPO_HOST = "github.com"
ALLOWED_API_HOST = "api.github.com"

# GitHub names: alphanumeric plus -_. ; owners may not start with '-'.
_NAME_RE = re.compile(r"^(?!-)[A-Za-z0-9._-]{1,100}$")

# Git refs cannot contain these characters / sequences (git-check-ref-format).
_REF_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f ~^:?*\[\\]|\.\.|@{|^/|/$|^\.|\.$|//")


def parse_repo_url(url: str) -> tuple[str, str]:
    """Parse a https://github.com/{owner}/{repo} URL into (owner, repo).

    Accepts an optional .git suffix and an optional /tree/<ref>[/dir] suffix
    (the ref/subdirectory in the URL is ignored — the caller passes them
    explicitly, so nothing selected by a deep-link is silently imported).
    Rejects every other host, scheme, credentials, fragments, traversal and
    non-tree path suffixes (blob/issues/wiki pages are not repository roots).
    """
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("Repository URL is missing or too long")
    url = url.strip()
    prefix = f"https://{ALLOWED_REPO_HOST}/"
    if not url.startswith(prefix):
        raise ValueError(
            f"Repository URL must start with https://{ALLOWED_REPO_HOST}/"
        )
    remainder = url[len(prefix):]
    if remainder.endswith(".git"):
        remainder = remainder[: -len(".git")]
    remainder = remainder.split("?")[0].split("#")[0]
    parts = [part for part in remainder.split("/") if part]
    if len(parts) < 2:
        raise ValueError("Repository URL must be github.com/{owner}/{repo}")
    owner, repo, *extra = parts
    if extra and extra[0] != "tree":
        raise ValueError("Repository URL must be github.com/{owner}/{repo}[/tree/...]")
    if len(extra) > 3:
        raise ValueError("Repository URL contains too many path segments")
    for part in (owner, repo):
        if part in ("", ".", "..") or not _NAME_RE.match(part):
            raise ValueError("Repository owner/name contain invalid characters")
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    return owner, repo


def validate_ref(ref: str) -> str:
    """Validate a branch/tag/SHA ref for safe use in an API path."""
    if not isinstance(ref, str):
        raise ValueError("Ref must be a string")
    ref = ref.strip()
    if not ref or len(ref) > 255:
        raise ValueError("Ref is missing or longer than 255 characters")
    if _REF_FORBIDDEN.search(ref):
        raise ValueError("Ref contains characters that are not valid in a git ref")
    return ref


COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def is_commit_sha(ref: str) -> bool:
    """True when the ref is already a full 40-character commit SHA."""
    return bool(COMMIT_SHA_RE.match(ref or ""))


def validate_patterns(patterns: list[str] | None, kind: str) -> list[str]:
    """Validate include/exclude path glob patterns (fnmatch, case-sensitive)."""
    if patterns is None:
        return []
    if not isinstance(patterns, list) or len(patterns) > 64:
        raise ValueError(f"{kind} must be a list with at most 64 patterns")
    validated = []
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"{kind} patterns must be non-empty strings")
        if len(pattern) > 512:
            raise ValueError(f"{kind} Patterns must be at most 512 characters")
        normalized = pattern.replace("\\", "/").strip()
        if normalized.startswith("/") or normalized.startswith("~"):
            raise ValueError(f"{kind} patterns must be repository-relative")
        if ".." in normalized.split("/"):
            raise ValueError(f"{kind} patterns must not contain path traversal")
        validated.append(normalized)
    return validated


def _matches(path: str, patterns: list[str]) -> bool:
    """fnmatch(path-like): '*' also spans '/', so 'docs/*' matches 'docs/a/b'."""
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


# ---------------------------------------------------------------------------
# File policy: allowlist formats, generated/vendor/secret/lockfile exclusions
# ---------------------------------------------------------------------------

# Phase 1 imports an explicit allowlist of text/code formats only. Binaries,
# media and archives are never accepted.
ALLOWED_EXTENSIONS = {
    ".bash": "text/plain",
    ".c": "text/plain",
    ".cc": "text/plain",
    ".cfg": "text/plain",
    ".cpp": "text/plain",
    ".cs": "text/plain",
    ".css": "text/css",
    ".csv": "text/csv",
    ".go": "text/plain",
    ".h": "text/plain",
    ".hpp": "text/plain",
    ".html": "text/plain",
    ".ini": "text/plain",
    ".java": "text/plain",
    ".js": "text/plain",
    ".json": "text/plain",
    ".jsx": "text/plain",
    ".kt": "text/plain",
    ".md": "text/markdown",
    ".php": "text/plain",
    ".py": "text/plain",
    ".rb": "text/plain",
    ".rs": "text/plain",
    ".rst": "text/plain",
    ".scss": "text/plain",
    ".sh": "text/plain",
    ".sql": "text/plain",
    ".svg": "text/plain",
    ".swift": "text/plain",
    ".toml": "text/plain",
    ".ts": "text/plain",
    ".tsx": "text/plain",
    ".txt": "text/plain",
    ".xml": "text/plain",
    ".yaml": "text/plain",
    ".yml": "text/plain",
}

# Extension-less build/config files that are still plain text.
ALLOWED_BASENAMES = {
    "Dockerfile": "text/plain",
    "Makefile": "text/plain",
}

# Generated, build output and vendor directories — nothing inside is imported.
EXCLUDED_DIR_NAMES = {
    ".cache",
    ".eggs",
    ".gradle",
    ".mypy_cache",
    ".next",
    ".npm",
    ".nuxt",
    ".pytest_cache",
    ".ruff_cache",
    ".sass-cache",
    ".terragrunt-cache",
    ".tox",
    ".venv",
    ".yarn",
    "__pycache__",
    "bower_components",
    "build",
    "coverage",
    "dep",
    "dist",
    "eggs",
    "envs",
    "node_modules",
    "obj",
    "out",
    "packages-lock",
    "site-packages",
    "target",
    "vendor",
    "venv",
}

# Lockfiles and other dependency-resolver outputs (generated, mostly noise).
LOCKFILE_NAMES = {
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "go.sum",
    "mix.lock",
    "npm-shrinkwrap.json",
    "package-lock.json",
    "pipfile.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "yarn.lock",
}

# Minified bundles are generated artifacts, not source.
BUNDLED_SUFFIXES = (".min.js", ".min.css", ".bundle.js", "-bundle.js")

# .git/ internals and system junk must never be imported.
ALWAYS_EXCLUDED_NAMES = {
    ".ds_store",
    ".lockfile",  # editor swap noise
    ".swp",
}

# Secret-like files are excluded by name pattern regardless of extension —
# their contents are never fetched, parsed, logged or embedded.
_SECRET_NAME_SUFFIXES = (
    # Key material / keystores / certificates-with-private-parts
    ".pem", ".key", ".p12", ".pfx", ".jks", ".kdbx", ".keystore",
)
_SECRET_NAME_HINTS = re.compile(
    r"(^|[/\-.])(id_rsa|id_dsa|id_ecdsa|id_ed25519|secrets?|credential)"
    r"|(_secret|_token|secret_key|private_key|access_token|refresh_token)"
    r"|(credentials)",
    re.IGNORECASE,
)


def _is_secret_like_name(lower_path: str) -> bool:
    name = lower_path.rsplit("/", 1)[-1]
    if name == ".env" or name.startswith(".env.") or name == ".envrc":
        return True
    if name in (".npmrc", ".pypirc", ".netrc", ".htpasswd") or name == "netrc":
        return True
    if name in ("secrets.json", "secrets.yml", "secrets.yaml", "settings_local.py"):
        return True
    if name.startswith("service-account") and name.endswith(".json"):
        return True
    if name.startswith("client_secret") and name.endswith(".json"):
        return True
    if any(name.endswith(suffix) for suffix in _SECRET_NAME_SUFFIXES):
        return True
    return bool(_SECRET_NAME_HINTS.search(name))


@dataclass(frozen=True)
class FileDecision:
    path: str
    size: int
    sha: str

    @property
    def file_type(self) -> str:
        name = self.path.rsplit("/", 1)[-1]
        suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if name in ALLOWED_BASENAMES:
            return ALLOWED_BASENAMES[name]
        if suffix in ALLOWED_EXTENSIONS:
            return ALLOWED_EXTENSIONS[suffix]
        return "text/plain"


@dataclass
class FilterOutcome:
    """Mutable accumulator: ``filter_tree`` builds it file by file."""
    included: list[FileDecision] = field(default_factory=list)
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (path, reason)
    total_bytes: int = 0


class RepoLimitError(ValueError):
    """The repository cannot be imported within configured limits."""


def filter_tree(
    entries,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    *,
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
) -> FilterOutcome:
    """Apply the import policy to GitHub tree entries.

    ``entries`` are objects with .path, .type ("blob"), .sha and .size
    (services.github_import.client.TreeEntry). Order is preserved so previews
    are deterministic.
    """
    include = include or []
    exclude = exclude or []
    max_files = max_files if max_files is not None else settings.GITHUB_IMPORT_MAX_FILES
    max_file_bytes = (
        max_file_bytes if max_file_bytes is not None else settings.GITHUB_IMPORT_MAX_FILE_BYTES
    )
    max_total_bytes = (
        max_total_bytes if max_total_bytes is not None else settings.GITHUB_IMPORT_MAX_TOTAL_BYTES
    )

    outcome = FilterOutcome()
    candidate_paths: list[tuple[str, int, str]] = []
    for entry in entries:
        path = entry.path
        reason = _exclude_reason(
            path,
            entry.type,
            include,
            exclude,
            entry.size,
            max_file_bytes,
        )
        if reason:
            outcome.excluded.append((path, reason))
            continue
        candidate_paths.append((path, entry.size, entry.sha))

    for path, size, sha in candidate_paths:
        if max_files is not None and len(outcome.included) >= max_files:
            raise RepoLimitError(
                f"Import includes more than {max_files} files; narrow include patterns or raise GITHUB_IMPORT_MAX_FILES"
            )
        if max_total_bytes is not None and outcome.total_bytes + size > max_total_bytes:
            raise RepoLimitError(
                f"Import exceeds the {max_total_bytes} byte repository limit; exclude paths to stay within it"
            )
        outcome.included.append(FileDecision(path=path, size=size, sha=sha))
        outcome.total_bytes += size
    return outcome


def _exclude_reason(
    path: str,
    entry_type: str,
    include: list[str],
    exclude: list[str],
    size: int | None,
    max_file_bytes: int,
) -> str | None:
    """Return an exclusion reason for a tree entry, or None to keep it."""
    if entry_type != "blob":
        return "not_a_file"
    if len(path) > 4096:
        return "path_too_long"
    parts = path.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts) or "\\" in path:
        return "unsafe_path"
    if any(control in path for control in "\x00\x01\x02\x03"):
        return "unsafe_path"
    lower_parts = [part.lower() for part in parts]
    name = parts[-1].lower()
    if parts[0].lower() == ".git":
        return "git_internal"
    if lower_parts[0] in ALWAYS_EXCLUDED_NAMES or name in ALWAYS_EXCLUDED_NAMES:
        return "system_file"
    if any(part in EXCLUDED_DIR_NAMES for part in lower_parts[:-1]):
        return "generated_or_vendor"
    if name in LOCKFILE_NAMES:
        return "lockfile"
    if any(name.endswith(suffix) for suffix in BUNDLED_SUFFIXES):
        return "minified_bundle"
    if _is_secret_like_name(path.lower()):
        return "secret_like"
    if include and not _matches(path, include):
        return "not_matched_by_include"
    if exclude and _matches(path, exclude):
        return "matched_by_exclude"
    if not _is_allowed_format(name):
        return "unsupported_format"
    if size is None:
        return "unknown_size"
    if max_file_bytes is not None and size > max_file_bytes:
        return "oversized_file"
    return None


def _is_allowed_format(name: str) -> bool:
    if name in {basename.lower() for basename in ALLOWED_BASENAMES}:
        return True
    if "." not in name:
        return False
    suffix = "." + name.rsplit(".", 1)[-1].lower()
    return suffix in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Content-level checks (run on fetched bytes at import time)
# ---------------------------------------------------------------------------

def looks_binary_content(data: bytes) -> bool:
    """Reject NUL-byte payloads (allowlisted extensions must still be text)."""
    return b"\x00" in data[:8192]


def decode_blob(data: bytes) -> bytes:
    """Decode GitHub blob content (base64 JSON field) with strict validation."""
    try:
        return base64.b64decode(data, validate=True)
    except (ValueError, TypeError):
        raise ValueError("Blob content is not valid base64")


SECRET_CONTENT_PATTERNS = (
    # AWS access key id (AWSKIA-style 20 uppercase/digit).
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    # GitHub tokens: ghp_, gho_, ghs_, ghs, ghu_, ghr_
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    # Slack bot/user tokens
    re.compile(r"\bxox[baprs]-[a-zA-Z0-9-]{10,}\b"),
    # Private key block headers
    re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY( BLOCK)?-----"
    ),
    # Google API keys
    re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    # Stripe restricted keys
    re.compile(r"\bsk_live_[a-zA-Z0-9]{10,}\b"),
)


def content_secret_scan(data: bytes) -> str | None:
    """Return a reason when fetched content looks like a secret, else None.

    Never returns (or logs) the matching content itself — only the pattern kind.
    High-precision patterns only; unknown formats should slip through rather
    than block ordinary source code.
    """
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return "undecodable"
    for pattern in SECRET_CONTENT_PATTERNS:
        match = pattern.search(text)
        if match:
            return pattern.pattern[:24].replace("\\b", "") + "_match"
    return None


def blob_sha256(data: bytes) -> str:
    """Content hash recorded for Phase 2 re-sync comparisons."""
    return hashlib.sha256(data).hexdigest()
