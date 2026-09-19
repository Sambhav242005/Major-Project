"""Agent pipeline package — re-exports original public API."""

from pipelines.agent.executor import execute_agent
from pipelines.agent.graph import _build_agent_graph, _get_graph
from pipelines.agent.state import AgentState, _add_trace
from pipelines.agent.types import AGENT_TYPES, get_agent_type_info

# Nodes (optional but kept for external use)
from pipelines.agent.nodes.eval import node_evaluate, node_refine
from pipelines.agent.nodes.lifecycle import node_build_prompt, node_initialize, node_post_process
from pipelines.agent.nodes.llm import node_execute_llm, node_execute_tool

MAX_TOOL_ITERATIONS = 3
MAX_RETRIES = 3

__all__ = [
    "AGENT_TYPES",
    "get_agent_type_info",
    "AgentState",
    "_add_trace",
    "_build_agent_graph",
    "_get_graph",
    "execute_agent",
    "node_initialize",
    "node_build_prompt",
    "node_execute_llm",
    "node_execute_tool",
    "node_post_process",
    "node_evaluate",
    "node_refine",
    "MAX_TOOL_ITERATIONS",
    "MAX_RETRIES",
]
