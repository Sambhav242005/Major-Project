"""Agent execution entry point."""

import time
from datetime import datetime, timezone
from typing import AsyncGenerator

from pipelines.agent.graph import _get_graph
from pipelines.agent.state import AgentState


async def execute_agent(
    agent_type: str,
    config: dict,
    input_data: dict,
    db_session=None,
    project_id: str = "",
) -> AsyncGenerator[dict, None]:
    """Execute an agent via LangGraph and yield trace events."""
    if agent_type == "google_meet":
        from services.google_meet import run_meeting_bot, GoogleMeetError

        all_traces: list[dict] = []

        async def progress(event: dict):
            all_traces.append(event)

        try:
            meet_link = str(input_data.get("meet_link") or input_data.get("link") or "")
            duration = int(input_data.get("duration") or input_data.get("duration_seconds") or 60)
            result = await run_meeting_bot(meet_link, duration, progress=progress)

            for trace_event in all_traces:
                yield trace_event
            yield {
                "step": "post_process", "status": "completed",
                "output": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            yield {
                "step": "complete", "status": "completed",
                "output": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except GoogleMeetError as e:
            err = {"step": "execution", "status": "error", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
            all_traces.append(err)
            yield err
        return

    graph = _get_graph()

    initial_state: AgentState = {
        "agent_type": agent_type,
        "config": config,
        "input_data": input_data,
        "system_prompt": "",
        "messages": [],
        "full_response": "",
        "result": {},
        "trace": [],
        "error": None,
        "start_time": time.time(),
        "tool_iterations": 0,
        "tool_call_history": [],
        "db_session": db_session,
        "project_id": project_id,
        "evaluation": {},
        "refinement": {},
    }

    all_traces = []
    async for event in graph.astream(initial_state):
        for node_name, state_update in event.items():
            if "trace" in state_update:
                new_traces = state_update["trace"][len(all_traces):]
                for trace_event in new_traces:
                    all_traces.append(trace_event)
                    yield trace_event
