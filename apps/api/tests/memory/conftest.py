"""Shared fixtures and helpers for memory tests."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

AGENT_ID = str(uuid.uuid4())
PROJECT_ID = str(uuid.uuid4())


def _make_mock_db():
    """Create a mock AsyncSession that captures added objects."""
    mock_db = AsyncMock()
    added = []

    def mock_add(obj):
        added.append(obj)

    mock_db.add = mock_add
    mock_db.flush = AsyncMock()
    mock_db._added = added
    return mock_db


def _mock_execute_result(scalars_list):
    """Create a mock result that returns scalars().all()."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = scalars_list
    mock_result.rowcount = len(scalars_list)
    return mock_result
