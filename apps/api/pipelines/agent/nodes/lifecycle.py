"""Lifecycle nodes: initialize, build_prompt, post_process."""

import json
from datetime import datetime, timezone

from core.security_utils import sanitize_for_llm, detect_injection
from pipelines.agent.state import AgentState, _add_trace
from pipelines.agent.types import get_agent_type_info
from pipelines.agent_tools import get_tool_schemas

MAX_TOOL_ITERATIONS = 3


async def node_initialize(state: AgentState) -> dict:
    """Validate input and initialize."""
    trace_update = _add_trace(state, "initialize", "running")

    clean_input = {k: v for k, v in state["input_data"].items() if not k.startswith("_")}
    user_input = sanitize_for_llm(json.dumps(clean_input, default=str))

    if detect_injection(user_input):
        return {
            **trace_update,
            "error": "Input rejected: potential prompt injection detected",
            "trace": state["trace"] + [{
                "step": "initialize", "status": "error",
                "error": "Input rejected: potential prompt injection detected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    type_info = get_agent_type_info(state["agent_type"])
    system_prompt = state["config"].get("system_prompt", type_info["system_prompt"])

    tool_schemas = get_tool_schemas()
    if tool_schemas:
        tool_descriptions = "\n".join(
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in tool_schemas
        )
        system_prompt += (
            f"\n\nYou have access to these tools:\n{tool_descriptions}\n"
            f"To use a tool, respond with a JSON block: "
            f'{{"tool": "tool_name", "arguments": {{...}}}}\n'
            f"You can use up to {MAX_TOOL_ITERATIONS} tools in sequence."
        )

    return {
        **trace_update,
        "system_prompt": system_prompt,
        "tool_iterations": 0,
        "tool_call_history": [],
        "trace": state["trace"] + [{
            "step": "initialize", "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }


async def node_build_prompt(state: AgentState) -> dict:
    """Build message array for LLM."""
    messages = [{"role": "system", "content": state["system_prompt"]}]

    memory_context = state["input_data"].get("_memory_context")
    if memory_context:
        messages.append({
            "role": "system",
            "content": (
                "You have the following memory from past interactions. "
                "Use it to inform your response, but do not repeat it back to the user.\n\n"
                f"{memory_context}"
            ),
        })

    if "context" in state["input_data"]:
        messages.append({
            "role": "system",
            "content": f"Additional context:\n{state['input_data']['context']}",
        })

    skills_context = state["input_data"].get("_skills_context")
    if skills_context:
        messages.append({
            "role": "system",
            "content": (
                "You have learned skills from past runs. Use them to improve your output.\n\n"
                f"{skills_context}"
            ),
        })

    clean_input = {k: v for k, v in state["input_data"].items() if not k.startswith("_")}
    user_input = sanitize_for_llm(json.dumps(clean_input, default=str))
    messages.append({"role": "user", "content": user_input})

    return {
        "messages": messages,
        "trace": state["trace"] + [{
            "step": "prompt_built", "status": "completed",
            "output": f"Messages prepared: {len(messages)} messages",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }


async def node_post_process(state: AgentState) -> dict:
    """Parse LLM output based on agent type."""
    result = {"response": state["full_response"]}
    agent_type = state["agent_type"]
    full_response = state["full_response"]

    if agent_type == "extractor":
        try:
            start = full_response.find("{")
            end = full_response.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(full_response[start:end])
                result["entities"] = parsed.get("entities", [])
                result["relationships"] = parsed.get("relationships", [])
        except json.JSONDecodeError:
            result["parse_error"] = "Could not parse JSON from response"

    elif agent_type == "reviewer":
        try:
            start = full_response.find("Score:")
            if start < 0:
                start = full_response.find("score:")
            if start >= 0:
                score_text = full_response[start:start + 50]
                score_num = "".join(c for c in score_text.split()[1] if c.isdigit())
                result["score"] = int(score_num) if score_num else None
        except (IndexError, ValueError):
            result["score"] = None

    if state.get("tool_call_history"):
        result["tool_calls"] = state["tool_call_history"]

    return {
        "result": result,
        "trace": state["trace"] + [{
            "step": "post_process", "status": "completed",
            "output": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
