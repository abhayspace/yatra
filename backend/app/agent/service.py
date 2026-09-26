"""High-level agent invocation used by the API layer."""

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import get_graph
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

    reply = ""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            reply = (
                msg.content
                if isinstance(msg.content, str)
                else str(msg.content)
            )
            break

    return {
        "reply": reply,
        "thread_id": thread_id,
        "requirements": result.get("requirements"),
    }
