"""Evaluation and refinement nodes."""

import logging
from datetime import datetime

from pipelines.agent.state import AgentState

logger = logging.getLogger(__name__)


async def node_evaluate(state: AgentState) -> dict:
    """Rule-based evaluation of agent output."""
    from pipelines.refinement.evaluation import _evaluate_output_rule_based

    result = state.get("result", {})
    agent_type = state["agent_type"]
    input_data = state.get("input_data", {})

    evaluation = _evaluate_output_rule_based(agent_type, result, input_data)

    return {
        "evaluation": evaluation,
        "trace": state["trace"] + [{
            "step": "evaluate", "status": "completed",
            "score": evaluation["score"],
            "details": evaluation.get("details", {}),
            "timestamp": datetime.utcnow().isoformat(),
        }],
    }


async def node_refine(state: AgentState) -> dict:
    """Run refinement cycle if score is below threshold."""
    from pipelines.refinement.gate import run_refinement_cycle

    evaluation = state.get("evaluation", {})
    score = evaluation.get("score", 1.0)
    agent_type = state["agent_type"]
    db = state.get("db_session")
    agent_id = state.get("input_data", {}).get("_agent_id")

    refinement_result = None
    if score < 0.7 and db and agent_id:
        try:
            refinement_result = await run_refinement_cycle(db, agent_id, agent_type)
        except Exception as e:
            logger.warning(f"Refinement failed: {e}")

    return {
        "refinement": refinement_result,
        "trace": state["trace"] + [{
            "step": "refine", "status": "completed",
            "refinement": refinement_result,
            "timestamp": datetime.utcnow().isoformat(),
        }],
    }
