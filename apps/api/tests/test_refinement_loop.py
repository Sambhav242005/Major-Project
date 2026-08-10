"""Refinement-loop regression tests — the two-split gate must be real.

Covers plan Phase 5:
- evaluate_on_split returns measured (non-0.5) scores when traces exist
- store_run_trace bumps helpful/harmful counters from measured score
- run_refinement_cycle gates on measured deltas, never placeholders
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models import AgentRunTrace, AgentSkill


def _make_trace(agent_id: str, score: float, output_text: str, input_text: str = "q"):
    return AgentRunTrace(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(agent_id),
        task_id=None,
        input_text=input_text,
        output_text=output_text,
        tool_calls=[],
        scores={"score": score},
        skills_used=[],
        created_at=__import__("datetime").datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_evaluate_on_split_scores_real_traces():
    """evaluate_on_split must score real traces, not return the 0.5 placeholder."""
    from pipelines.agent_refinement import evaluate_on_split

    agent_id = str(uuid.uuid4())
    mock_db = AsyncMock()

    # eval set lookup: no rows -> eval_inputs empty (fall back to all traces)
    eval_result = MagicMock()
    eval_result.all.return_value = []
    # traces: one good, one bad extractor run
    traces_result = MagicMock()
    traces_result.scalars.return_value.all.return_value = [
        _make_trace(agent_id, 0.9, '{"entities": [{"name": "A"}], "relationships": [{}]}'),
        _make_trace(agent_id, 0.2, '{"parse_error": "bad"}'),
    ]

    def mock_execute(stmt):
        if "refinement_eval_sets" in str(stmt):
            return eval_result
        return traces_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    score = await evaluate_on_split(mock_db, agent_id, "extractor", "held_in", limit=5)

    assert score != 0.5  # measured, not placeholder
    assert 0.0 < score <= 1.0


@pytest.mark.asyncio
async def test_evaluate_on_split_returns_neutral_when_no_data():
    """No traces at all -> true neutral 0.5 (the only legitimate 0.5)."""
    from pipelines.agent_refinement import evaluate_on_split

    agent_id = str(uuid.uuid4())
    mock_db = AsyncMock()

    eval_result = MagicMock()
    eval_result.all.return_value = []
    traces_result = MagicMock()
    traces_result.scalars.return_value.all.return_value = []

    def mock_execute(stmt):
        if "refinement_eval_sets" in str(stmt):
            return eval_result
        return traces_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    score = await evaluate_on_split(mock_db, agent_id, "extractor", "held_in")

    assert score == 0.5


@pytest.mark.asyncio
async def test_store_run_trace_bumps_counters():
    """helpful/harmful counters increment from measured score."""
    from pipelines.agent_refinement import store_run_trace

    agent_id = str(uuid.uuid4())
    skill_id = str(uuid.uuid4())
    mock_db = AsyncMock()

    skill = AgentSkill(
        id=uuid.UUID(skill_id),
        agent_id=uuid.UUID(agent_id),
        skill_type="prompt_hint",
        content="test skill",
        helpful_count=0,
        harmful_count=0,
        success_count=0,
        failure_count=0,
    )

    skill_result = MagicMock()
    skill_result.scalars.return_value.all.return_value = [skill]

    def mock_execute(stmt):
        return skill_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    await store_run_trace(
        db=mock_db,
        agent_id=agent_id,
        task_id=str(uuid.uuid4()),
        input_text="q",
        output_text="good response with content",
        tool_calls=[],
        scores={"score": 0.9},
        skills_used=[skill_id],
    )

    assert skill.helpful_count == 1
    assert skill.success_count == 1
    assert skill.harmful_count == 0


@pytest.mark.asyncio
async def test_run_refinement_cycle_uses_measured_deltas():
    """The gate receives measured deltas, not hardcoded 0.1/0.0."""
    from pipelines.agent_refinement import run_refinement_cycle

    agent_id = str(uuid.uuid4())
    mock_db = AsyncMock()

    with patch(
        "pipelines.agent_refinement.mine_failures", new_callable=AsyncMock
    ) as mock_mine, patch(
        "pipelines.agent_refinement.propose_skill_delta", new_callable=AsyncMock
    ) as mock_propose, patch(
        "pipelines.agent_refinement.evaluate_on_split", new_callable=AsyncMock
    ) as mock_eval, patch(
        "pipelines.agent_refinement.apply_delta", new_callable=AsyncMock
    ) as mock_apply:
        mock_mine.return_value = [{"scores": {"entity_count": 0.1}}]
        mock_propose.return_value = {
            "action": "add",
            "skill_id": None,
            "content": "extract more",
            "reason": "low entity count",
            "before": None,
        }
        mock_eval.side_effect = [0.7, 0.6]  # held_in, held_out
        mock_apply.return_value = True

        result = await run_refinement_cycle(mock_db, agent_id, "extractor")

        assert result["held_in_score"] == 0.7
        assert result["held_out_score"] == 0.6
        # deltas are computed from measured scores, not hardcoded
        assert result["held_in_delta"] == pytest.approx(0.2)  # 0.7 - 0.5
        assert result["held_out_delta"] == pytest.approx(-0.1)  # 0.6 - 0.7
        mock_apply.assert_called_once()
