"""Yatra AI planning graph.

Flow:
    START → extract_requirements
          → (needs_clarification) END        [question returned to user]
          → planner ⇄ tools                  [ReAct tool-use loop]
          → verify
          → (issues found, under cap) planner[rewrite with feedback]
          → END

The verify→planner loop is bounded by ``agent_max_verify_loops`` and the
whole run by ``agent_recursion_limit`` — the graph can never spin forever.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.checkpoint import get_checkpointer
from app.agent.nodes import (
    create_extract_node,
    create_planner_node,
    create_verify_node,
)
from app.agent.state import AgentState
from app.agent.tools import get_tools
from app.config import get_settings


def _route_after_extract(state: AgentState):
    if state.get("needs_clarification"):
        return END
    return "planner"


def _route_after_planner(state: AgentState):
    messages = state.get("messages", [])
    if messages and getattr(messages[-1], "tool_calls", None):
        return "tools"
    return "verify"


def _route_after_verify(state: AgentState):
    if state.get("validation_feedback"):
        return "planner"
    return END


_graph = None


def get_graph():
    global _graph
    if _graph is not None:
        return _graph

    settings = get_settings()
    tools = get_tools()

    builder = StateGraph(AgentState)
    builder.add_node("extract", create_extract_node())
    builder.add_node("planner", create_planner_node(tools))
    builder.add_node("tools", ToolNode(tools))
    builder.add_node(
        "verify", create_verify_node(settings.agent_max_verify_loops)
    )

    builder.add_edge(START, "extract")
    builder.add_conditional_edges(
        "extract",
        _route_after_extract,
        {"planner": "planner", END: END},
    )
    builder.add_conditional_edges(
        "planner",
        _route_after_planner,
        {"tools": "tools", "verify": "verify"},
    )
    builder.add_edge("tools", "planner")
    builder.add_conditional_edges(
        "verify",
        _route_after_verify,
        {"planner": "planner", END: END},
    )

    _graph = builder.compile(checkpointer=get_checkpointer())
    return _graph
