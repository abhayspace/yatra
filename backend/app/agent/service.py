"""High-level agent invocation used by the API layer."""

from langchain_core.messages import HumanMessage

from app.agent.graph import get_graph
from app.agent.nodes import assemble_reply
from app.config import get_settings


def run_agent_turn(user_id: str, thread_id: str, message: str) -> dict:
    """Run one conversational turn of the planning agent.

    ``thread_id`` scopes the checkpointed conversation — reusing it enables
    adaptive replanning (the agent sees the previous plan in history).
    """
    settings = get_settings()
    graph = get_graph()

    config = {
        "configurable": {"thread_id": f"{user_id}:{thread_id}"},
        "recursion_limit": settings.agent_recursion_limit,
    }

    result = graph.invoke(
        {"messages": [HumanMessage(content=message)]},
        config=config,
    )

    reply = assemble_reply(result.get("messages", []))
    if not reply.strip():
        reply = (
            "I hit a snag generating that plan — the model returned an "
            "empty response. Please try again; if it keeps happening, the "
            "LLM quota may be exhausted for today."
        )

    return {
        "reply": reply,
        "thread_id": thread_id,
        "requirements": result.get("requirements"),
    }
