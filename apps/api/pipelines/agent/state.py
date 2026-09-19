"""Agent LangGraph state."""

from datetime import datetime
from typing import Any, TypedDict


class AgentState(TypedDict):
    agent_type: str
    config: dict
    input_data: dict
    system_prompt: str
    messages: list[dict]
    full_response: str
    result: dict
    trace: list[dict]
    error: str | None
    start_time: float
    tool_iterations: int
    tool_call_history: list[dict]
    db_session: Any
    project_id: str
    evaluation: dict
    refinement: dict


def _add_trace(state: AgentState, step: str, status: str, **kwargs) -> dict:
    event = {
        "step": step,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs,
    }
    return {"trace": state["trace"] + [event]}
