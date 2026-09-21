"""LangGraph graph construction."""

from langgraph.graph import StateGraph, END

from pipelines.agent.nodes.eval import node_evaluate, node_refine
from pipelines.agent.nodes.lifecycle import node_build_prompt, node_initialize, node_post_process
from pipelines.agent.nodes.llm import node_execute_llm, node_execute_tool
from pipelines.agent.state import AgentState


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
        if not state.get("full_response") and state.get("tool_iterations", 0) > 0:
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
