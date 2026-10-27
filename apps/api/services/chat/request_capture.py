"""Short-lived in-process store for captured model request snapshots.

Retention semantics (TODO 2.24, Phase 1): snapshots live only in this
process's memory — no database table. Each entry:
- is keyed by an opaque per-request UUID exposed to the owning chat turn,
- is evicted after ``SNAPSHOT_TTL_SECONDS`` (30 minutes, refreshed on nothing —
  a snapshot's clock starts at registration),
- is evicted oldest-first once ``MAX_SNAPSHOTS`` (200) entries exist in the
  process,
- disappears entirely on process restart,
- is surfaced only through ``get_snapshot_for_project``, which refuses every
  caller that is not a member of the originating project through the standard
  ``core.deps#get_project_id`` project resolution plus a chat-session
  membership check (the session must still exist in that project).

Expired/evicted/foreign lookups all return ``None`` (the router answers 404),
so callers cannot distinguish a missing snapshot from one they may not see.
"""

import time
from collections import OrderedDict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

SNAPSHOT_TTL_SECONDS = 30 * 60
MAX_SNAPSHOTS = 200

# request_id -> (expires_at_monotonic, snapshot)
_entries: "OrderedDict[str, tuple[float, dict[str, Any]]]" = OrderedDict()


def _now() -> float:
    return time.monotonic()


def register_snapshot(snapshot: dict[str, Any]) -> None:
    """Store one finished snapshot; silently refuses incomplete captures."""
    request_id = snapshot.get("request_id")
    if not request_id:
        return
    now = _now()
    # Drop expired entries.
    for key in [k for k, (expires, _) in _entries.items() if expires <= now]:
        _entries.pop(key, None)
    _entries[request_id] = (now + SNAPSHOT_TTL_SECONDS, snapshot)
    # Enforce the LRU cap, evicting the oldest first.
    while len(_entries) > MAX_SNAPSHOTS:
        _entries.popitem(last=False)


async def get_snapshot_for_project(
    db: AsyncSession,
    request_id: str,
    project_id: str,
) -> dict[str, Any] | None:
    """Return the snapshot when it exists and belongs to the calling project.

    Authorization layers:
      1. the resolved project (``get_project_id`` membership check) must equal
         the snapshot's recorded ``project_id``;
      2. the originating chat session must still exist inside that project
         (``get_session`` matches on ``session_id`` + ``project_id``), which
         ties read access to authorized project/chat membership instead of
         knowing an opaque request id.
    """
    entry = _entries.get(request_id)
    if entry is None:
        return None
    expires_at, snapshot = entry
    if expires_at <= _now():
        _entries.pop(request_id, None)
        return None
    if snapshot.get("project_id") != project_id:
        return None

    from .sessions import get_session

    session = await get_session(db, snapshot.get("session_id") or "", project_id)
    if session is None:
        return None
    return snapshot


def clear_store() -> None:
    """Test helper: drop every snapshot (also documents memory-only retention)."""
    _entries.clear()
