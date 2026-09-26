"""High-level agent invocation used by the API layer."""

import asyncio

from langchain_core.messages import HumanMessage

from app.agent.checkpoint import ensure_checkpointer_setup
from app.agent.graph import get_graph
from app.agent.nodes import assemble_reply
from app.config import get_settings
from app.db.supabase import get_service_client


def _load_profile_prefs(user_id: str) -> dict | None:
    """Fetch the user's saved travel preferences (None for guests)."""
    if user_id.startswith("guest:"):
        return None
    try:
        res = (
            get_service_client()
            .table("travel_profiles")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


async def run_agent_turn(user_id: str, thread_id: str, message: str) -> dict:
    """Run one conversational turn of the planning agent.

    ``thread_id`` scopes the checkpointed conversation — reusing it enables
    adaptive replanning (the agent sees the previous plan in history).
    """
    settings = get_settings()
    graph = get_graph()
    await ensure_checkpointer_setup()

    config = {
        "configurable": {"thread_id": f"{user_id}:{thread_id}"},
        "recursion_limit": settings.agent_recursion_limit,
    }

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=message)],
            "profile_prefs": await asyncio.to_thread(
                _load_profile_prefs, user_id
            ),
        },
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
