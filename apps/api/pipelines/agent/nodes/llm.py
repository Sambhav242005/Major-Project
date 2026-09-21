"""LLM execution and tool-calling nodes."""

import json
import logging
import time
from datetime import datetime, timezone

from pipelines.agent.state import AgentState
from pipelines.agent_tools import execute_tool
from pipelines.llm_client import chat_completion_stream

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MAX_TOOL_ITERATIONS = 3


async def node_execute_llm(state: AgentState) -> dict:
    """Execute LLM call with retry logic."""
    start = time.time()
    full_response = ""

    for attempt in range(MAX_RETRIES):
        try:
            async for chunk in chat_completion_stream(state["messages"], model=state["config"].get("model")):
                if isinstance(chunk, dict) and "content" in chunk:
                    full_response += chunk["content"]
                elif isinstance(chunk, str):
                    full_response += chunk

            elapsed = time.time() - start
            return {
                "full_response": full_response,
                "trace": state["trace"] + [{
                    "step": "llm_execution", "status": "completed",
                    "output": full_response,
                    "elapsed_seconds": round(elapsed, 2),
                    "attempt": attempt + 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            }
        except Exception as e:
            logger.warning(f"LLM execution attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)
            else:
                return {
                    "error": str(e),
                    "trace": state["trace"] + [{
                        "step": "llm_execution", "status": "error",
                        "error": str(e),
                        "attempts": MAX_RETRIES,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }],
                }


async def node_execute_tool(state: AgentState) -> dict:
    """Check if LLM response contains a tool call, execute it."""
    full_response = state["full_response"]
    tool_call_history = list(state.get("tool_call_history", []))
    iterations = state.get("tool_iterations", 0)

    tool_call = None
    try:
        start = full_response.find("{")
        end = full_response.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(full_response[start:end])
            if "tool" in parsed and "arguments" in parsed:
                tool_call = parsed
    except (json.JSONDecodeError, ValueError):
        pass

    if not tool_call or iterations >= MAX_TOOL_ITERATIONS:
        return {
            "tool_iterations": iterations,
            "tool_call_history": tool_call_history,
            "trace": state["trace"] + [{
                "step": "tool_check", "status": "completed",
                "tool_found": False,
                "iterations_used": iterations,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    tool_name = tool_call["tool"]
    arguments = tool_call["arguments"]

    result_str = await execute_tool(
        tool_name=tool_name,
        arguments=arguments,
        project_id=state.get("project_id", ""),
        db=state.get("db_session"),
    )

    tool_call_history.append({
        "tool": tool_name,
        "arguments": arguments,
        "result": result_str[:2000],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    new_messages = state["messages"] + [
        {"role": "assistant", "content": full_response},
        {"role": "user", "content": f"Tool result from {tool_name}:\n{result_str}\n\nNow provide your final answer based on this tool result."},
    ]

    return {
        "messages": new_messages,
        "tool_iterations": iterations + 1,
        "tool_call_history": tool_call_history,
        "full_response": "",
        "trace": state["trace"] + [{
            "step": "tool_execution", "status": "completed",
            "tool": tool_name,
            "arguments": arguments,
            "result_preview": result_str[:500],
            "iteration": iterations + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
