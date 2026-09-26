from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Shared state across the Yatra AI planning graph."""

    messages: Annotated[list[AnyMessage], add_messages]

    # Structured requirements extracted from the conversation.
    requirements: dict[str, Any]

    # Set by the extraction node when a clarifying question is needed.
    needs_clarification: bool

    # Feedback written by the verifier when the plan fails checks.
    validation_feedback: str

    # Bounded verify→plan refinement loop counter.
    verify_count: int
