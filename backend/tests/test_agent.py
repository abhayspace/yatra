"""Unit tests for graph routing and reply assembly — no LLM calls."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

from app.agent.graph import (
    _route_after_extract,
    _route_after_planner,
    _route_after_verify,
)
from app.agent.nodes import assemble_reply


# ── Routing ──────────────────────────────────────────────────────────────

def test_extract_routes_to_end_on_clarification():
    assert _route_after_extract({"needs_clarification": True}) == END


def test_extract_routes_to_planner():
    assert _route_after_extract({"needs_clarification": False}) == "planner"
    assert _route_after_extract({}) == "planner"


def test_planner_routes_to_tools_on_tool_calls():
    msg = AIMessage(
        content="",
        tool_calls=[{"id": "1", "name": "calculate", "args": {}}],
    )
    assert _route_after_planner({"messages": [msg]}) == "tools"


def test_planner_routes_to_verify_on_final_text():
    assert _route_after_planner({"messages": [AIMessage(content="plan")]}) == "verify"


def test_verify_loops_on_feedback_ends_when_clean():
    assert _route_after_verify({"validation_feedback": "fix X"}) == "planner"
    assert _route_after_verify({"validation_feedback": None}) == END
    assert _route_after_verify({}) == END


# ── Reply assembly ───────────────────────────────────────────────────────

def test_assemble_simple_reply():
    msgs = [HumanMessage(content="hi"), AIMessage(content="Hello!")]
    assert assemble_reply(msgs) == "Hello!"


def test_assemble_plan_split_across_tool_call():
    """Plan header in msg A, tool call runs, continuation in msg B — merge."""
    msgs = [
        HumanMessage(content="plan a trip"),
        AIMessage(
            content=[{"type": "text", "text": "# ✈️ Your Personalized Trip Plan\n\n## 🧠 Trip Summary\nDestination: Shimla"}],
            tool_calls=[{"id": "t1", "name": "calculate", "args": {}}],
        ),
        ToolMessage(content="43000", tool_call_id="t1"),
        AIMessage(content="## 💰 Budget Breakdown\n| TOTAL | ₹43,000 |"),
    ]
    reply = assemble_reply(msgs)
    assert "Trip Summary" in reply
    assert "₹43,000" in reply  # continuation merged


def test_assemble_full_rewrite_wins():
    """If the last AI message is itself a complete plan, use it alone."""
    msgs = [
        HumanMessage(content="plan"),
        AIMessage(content="# ✈️ Plan v1\npartial"),
        HumanMessage(content="feedback fix"),
        AIMessage(content="# ✈️ Plan v2\ncomplete rewrite"),
    ]
    reply = assemble_reply(msgs)
    assert "v2" in reply and "v1" not in reply


def test_assemble_skips_tool_messages_and_empty():
    msgs = [
        HumanMessage(content="hi"),
        AIMessage(content="", tool_calls=[{"id": "t", "name": "x", "args": {}}]),
        ToolMessage(content="tool output", tool_call_id="t"),
        AIMessage(content="Done."),
    ]
    assert assemble_reply(msgs) == "Done."


def test_assemble_empty_state():
    assert assemble_reply([]) == ""
    assert assemble_reply([HumanMessage(content="x")]) == ""


def test_assemble_gemini_list_content():
    """Gemini returns content as a list of typed parts."""
    msgs = [
        HumanMessage(content="hi"),
        AIMessage(content=[{"type": "text", "text": "Answer here."}]),
    ]
    assert assemble_reply(msgs) == "Answer here."
