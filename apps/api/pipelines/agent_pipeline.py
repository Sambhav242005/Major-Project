"""Agent pipeline — LangGraph state machine with tool-calling, retry, and traces."""

import json
import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator, TypedDict

from langgraph.graph import StateGraph, END

from pipelines.llm_client import chat_completion_stream, chat_completion
from pipelines.agent_tools import execute_tool, get_tool_schemas, TOOL_REGISTRY
from pipelines.agent_refinement import (
    _evaluate_output_rule_based, store_run_trace, run_refinement_cycle,
)
from core.security_utils import sanitize_for_llm, detect_injection

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 3
MAX_RETRIES = 3


# --- Agent type definitions ---

AGENT_TYPES = {
    "summarizer": {
        "name": "Document Summarizer",
        "description": "Summarizes documents and extracts key points",
        "system_prompt": (
            "You are a document summarizer. Given a document or chunk of text, "
            "provide a concise summary highlighting the key points, entities, "
            "and relationships mentioned. Be factual and precise. "
            "Use the search_chunks tool to find relevant content before summarizing."
        ),
    },
    "extractor": {
        "name": "Entity Extractor",
        "description": "Extracts entities and relationships from text",
        "system_prompt": (
            "You are an entity extraction specialist. Given text, extract all "
            "named entities (people, organizations, locations, concepts, events) "
            "and the relationships between them. Use the store_entities tool to "
            "save extracted data to the knowledge base."
        ),
    },
    "qa": {
        "name": "Q&A Agent",
        "description": "Answers questions based on the knowledge base",
        "system_prompt": (
            "You are a knowledge base Q&A agent. Answer questions using only "
            "the provided context. Use search_chunks to find relevant information. "
            "Cite your sources when possible. If the context doesn't contain enough "
            "information, say so."
        ),
    },
    "reviewer": {
        "name": "Content Reviewer",
        "description": "Reviews and quality-scores content",
        "system_prompt": (
            "You are a content quality reviewer. Analyze the given text for "
            "accuracy, completeness, and clarity. Provide a quality score "
            "(1-10) and specific feedback on what could be improved."
        ),
    },
    "researcher": {
        "name": "Research Agent",
        "description": "Cross-project research using shared memories and knowledge graph",
        "system_prompt": (
            "You are a research agent. You have access to memories from this project "
            "and shared memories from other projects. Use search_chunks and get_entity "
            "tools to find information. Synthesize findings from multiple sources. "
            "Always cite which project shared memories came from."
        ),
    },
}


def get_agent_type_info(agent_type: str) -> dict:
    return AGENT_TYPES.get(agent_type, {
        "name": agent_type,
        "description": f"Custom agent type: {agent_type}",
        "system_prompt": f"You are a {agent_type} agent. Process the input and provide useful output.",
    })


# --- LangGraph state ---

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


# --- Graph nodes ---

def _add_trace(state: AgentState, step: str, status: str, **kwargs) -> dict:
    event = {
        "step": step,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs,
    }
    return {"trace": state["trace"] + [event]}


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
                "timestamp": datetime.utcnow().isoformat(),
            }],
        }

    type_info = get_agent_type_info(state["agent_type"])
    system_prompt = state["config"].get("system_prompt", type_info["system_prompt"])

    # Inject tool schemas into system prompt
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
            "timestamp": datetime.utcnow().isoformat(),
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
            "timestamp": datetime.utcnow().isoformat(),
        }],
    }


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
                    "timestamp": datetime.utcnow().isoformat(),
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
                        "timestamp": datetime.utcnow().isoformat(),
                    }],
                }


async def node_execute_tool(state: AgentState) -> dict:
    """Check if LLM response contains a tool call, execute it."""
    full_response = state["full_response"]
    tool_call_history = list(state.get("tool_call_history", []))
    iterations = state.get("tool_iterations", 0)

    # Try to parse tool call from response
    tool_call = None
    try:
        # Look for JSON tool call in response
        start = full_response.find("{")
        end = full_response.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(full_response[start:end])
            if "tool" in parsed and "arguments" in parsed:
                tool_call = parsed
    except (json.JSONDecodeError, ValueError):
        pass

    if not tool_call or iterations >= MAX_TOOL_ITERATIONS:
        # No tool call or max iterations reached — proceed to post_process
        return {
            "tool_iterations": iterations,
            "tool_call_history": tool_call_history,
            "trace": state["trace"] + [{
                "step": "tool_check", "status": "completed",
                "tool_found": False,
                "iterations_used": iterations,
                "timestamp": datetime.utcnow().isoformat(),
            }],
        }

    # Execute the tool
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
        "timestamp": datetime.utcnow().isoformat(),
    })

    # Append tool result to messages and re-run LLM
    new_messages = state["messages"] + [
        {"role": "assistant", "content": full_response},
        {"role": "user", "content": f"Tool result from {tool_name}:\n{result_str}\n\nNow provide your final answer based on this tool result."},
    ]

    return {
        "messages": new_messages,
        "tool_iterations": iterations + 1,
        "tool_call_history": tool_call_history,
        "full_response": "",  # Reset for next LLM call
        "trace": state["trace"] + [{
            "step": "tool_execution", "status": "completed",
            "tool": tool_name,
            "arguments": arguments,
            "result_preview": result_str[:500],
            "iteration": iterations + 1,
            "timestamp": datetime.utcnow().isoformat(),
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

    # Include tool call history in result
    if state.get("tool_call_history"):
        result["tool_calls"] = state["tool_call_history"]

    return {
        "result": result,
        "trace": state["trace"] + [{
            "step": "post_process", "status": "completed",
            "output": result,
            "timestamp": datetime.utcnow().isoformat(),
        }],
    }


async def node_evaluate(state: AgentState) -> dict:
    """Rule-based evaluation of agent output."""
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


# --- Build the graph ---

def _build_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("initialize", node_initialize)
    graph.add_node("build_prompt", node_build_prompt)
    graph.add_node("execute_llm", node_execute_llm)
    graph.add_node("execute_tool", node_execute_tool)
    graph.add_node("post_process", node_post_process)
    graph.add_node("evaluate", node_evaluate)
    graph.add_node("refine", node_refine)

    graph.set_entry_point("initialize")

    def after_initialize(state: AgentState):
        if state.get("error"):
            return END
        return "build_prompt"

    graph.add_conditional_edges("initialize", after_initialize, {
        "build_prompt": "build_prompt",
        END: END,
    })

    graph.add_edge("build_prompt", "execute_llm")

    def after_llm(state: AgentState):
        if state.get("error"):
            return END
        return "execute_tool"

    graph.add_conditional_edges("execute_llm", after_llm, {
        "execute_tool": "execute_tool",
        END: END,
    })

    def after_tool(state: AgentState):
        # If there's a new message (tool was executed), go back to LLM
        if state.get("messages") and len(state.get("messages", [])) > len(state.get("input_data", {}).get("_original_messages", [])):
            return "execute_llm"
        return "post_process"

    graph.add_conditional_edges("execute_tool", after_tool, {
        "execute_llm": "execute_llm",
        "post_process": "post_process",
    })

    graph.add_edge("post_process", "evaluate")

    graph.add_edge("evaluate", "refine")

    graph.add_edge("refine", END)

    return graph.compile()


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_agent_graph()
    return _compiled_graph


async def execute_agent(
    agent_type: str,
    config: dict,
    input_data: dict,
    db_session=None,
    project_id: str = "",
) -> AsyncGenerator[dict, None]:
    """Execute an agent via LangGraph and yield trace events."""
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

    # Run the graph and yield events as they're produced
    final_state = None
    async for event in graph.astream(initial_state):
        for node_name, state_update in event.items():
            if "trace" in state_update:
                new_traces = state_update["trace"][len(final_state["trace"]) if final_state else 0:]
                for trace_event in new_traces:
                    yield trace_event
            final_state = state_update

    if final_state and not final_state.get("trace"):
        for trace_event in final_state.get("trace", []):
            yield trace_event
