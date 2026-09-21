"""Rule-based evaluation and split scoring."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentRunTrace, RefinementEvalSet


def _evaluate_output_rule_based(agent_type: str, output: dict, input_data: dict) -> dict:
    """Rule-based evaluation — deterministic, not LLM-dependent."""
    scores = {}

    if agent_type == "extractor":
        entities = output.get("entities", [])
        relationships = output.get("relationships", [])
        scores["entity_count"] = min(len(entities) / 5, 1.0)
        scores["has_relationships"] = 1.0 if relationships else 0.0
        scores["parse_success"] = 0.0 if output.get("parse_error") else 1.0
        scores["score"] = (
            scores["entity_count"] * 0.4
            + scores["has_relationships"] * 0.3
            + scores["parse_success"] * 0.3
        )

    elif agent_type == "summarizer":
        response = output.get("response", "")
        scores["length"] = min(len(response) / 200, 1.0) if response else 0.0
        scores["has_content"] = 1.0 if len(response) > 50 else 0.0
        scores["score"] = scores["length"] * 0.5 + scores["has_content"] * 0.5

    elif agent_type == "qa":
        response = output.get("response", "")
        scores["has_citations"] = 1.0 if "[" in response else 0.0
        scores["length"] = min(len(response) / 100, 1.0) if response else 0.0
        scores["score"] = scores["has_citations"] * 0.5 + scores["length"] * 0.5

    elif agent_type == "reviewer":
        score = output.get("score")
        if score and 1 <= score <= 10:
            scores["valid_score"] = 1.0
            scores["score"] = 1.0
        else:
            scores["valid_score"] = 0.0
            scores["score"] = 0.0

    else:
        response = output.get("response", "")
        scores["has_content"] = 1.0 if len(response) > 20 else 0.0
        scores["score"] = scores["has_content"]

    return {"score": scores.get("score", 0.0), "details": scores}


async def evaluate_on_split(
    db: AsyncSession,
    agent_id: str,
    agent_type: str,
    split: str,
    limit: int = 5,
) -> float:
    """Evaluate agent quality on a held-in or held-out split."""
    stmt = select(RefinementEvalSet.input_text).where(
        RefinementEvalSet.agent_id == uuid.UUID(agent_id),
        RefinementEvalSet.split == split,
    )
    result = await db.execute(stmt)
    eval_inputs = [row[0] for row in result.all()]

    traces_stmt = (
        select(AgentRunTrace)
        .where(AgentRunTrace.agent_id == uuid.UUID(agent_id))
        .order_by(AgentRunTrace.created_at.desc())
        .limit(50)
    )
    traces_result = await db.execute(traces_stmt)
    traces = traces_result.scalars().all()

    scored = 0.0
    count = 0
    for t in traces:
        if eval_inputs and t.input_text not in eval_inputs:
            continue
        if not t.output_text:
            continue
        try:
            output = json.loads(t.output_text) if t.output_text.startswith("{") else {"response": t.output_text}
        except json.JSONDecodeError:
            output = {"response": t.output_text}
        score = _evaluate_output_rule_based(agent_type, output, {"input_text": t.input_text})
        scored += score["score"]
        count += 1
        if count >= limit:
            break

    if count == 0:
        return 0.5
    return scored / count
