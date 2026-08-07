"""Tests for dashboard service — summary stats."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_summary_returns_all_fields():
    """get_summary should return documents, entities, relationships, activity."""
    from services.dashboard import get_summary

    mock_db = AsyncMock()
    project_id = str(uuid.uuid4())

    # Mock all the query results
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("processed", 5),
        ("pending", 2),
        ("failed", 1),
    ]

    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar.return_value = 10

    mock_activity_result = MagicMock()
    mock_activity_result.scalars.return_value.all.return_value = []

    mock_failed_result = MagicMock()
    mock_failed_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return mock_result
        elif call_count <= 6:
            return mock_scalar_result
        elif call_count == 7:
            return mock_activity_result
        else:
            return mock_failed_result

    mock_db.execute = mock_execute

    result = await get_summary(mock_db, project_id)

    assert "documents" in result
    assert "total_documents" in result
    assert "total_entities" in result
    assert "total_relationships" in result
    assert "recent_activity" in result
    assert "failed_documents" in result
    assert "pipeline_health" in result
    assert result["documents"]["processed"] == 5
    assert result["documents"]["pending"] == 2
    assert result["documents"]["failed"] == 1


@pytest.mark.asyncio
async def test_get_summary_pipeline_health_calculation():
    """Pipeline health success_rate should be calculated correctly."""
    from services.dashboard import get_summary

    mock_db = AsyncMock()
    project_id = str(uuid.uuid4())

    # Mock: 8 processed, 2 pending, 0 failed
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("processed", 8),
        ("pending", 2),
    ]

    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar.return_value = 10

    mock_activity_result = MagicMock()
    mock_activity_result.scalars.return_value.all.return_value = []

    mock_failed_result = MagicMock()
    mock_failed_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return mock_result
        elif call_count <= 6:
            return mock_scalar_result
        elif call_count == 7:
            return mock_activity_result
        else:
            return mock_failed_result

    mock_db.execute = mock_execute

    result = await get_summary(mock_db, project_id)

    assert result["pipeline_health"]["success_rate"] == 80.0
    assert result["pipeline_health"]["queue_depth"] == 2
    assert result["pipeline_health"]["failed_count"] == 0
