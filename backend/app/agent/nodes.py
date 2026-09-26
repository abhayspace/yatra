"""Graph nodes: requirements extraction → planning → verification."""

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_llm_models
from app.agent.prompts import (
    EXTRACTION_PROMPT,
    SYSTEM_PROMPT,
    VERIFICATION_PROMPT,
)

# ── Structured schemas ───────────────────────────────────────────────────

class TravelRequirements(BaseModel):
    """Structured travel constraints extracted from the conversation."""

    origin: str | None = None
    destination: str | None = None
    travel_dates: str | None = None
    duration_days: int | None = None
    travelers: int | None = None
    budget_total: float | None = None
    currency: str | None = None
    traveler_type: str | None = None
    interests: list[str] = Field(default_factory=list)
    food_preferences: str | None = None
    accommodation_preferences: str | None = None
    transportation_preferences: str | None = None
    pace: str | None = None
    accessibility: str | None = None
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    other_constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarifying_question: str | None = None
    is_plan_request: bool = True


class PlanVerification(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    claimed_total_cost: float | None = None


# ── Helpers ──────────────────────────────────────────────────────────────

def _latest_human_message(state) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return _msg_text(msg)
    return ""


def _msg_text(msg) -> str:
    """Extract plain text from a message (Gemini returns content as blocks)."""
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)
    return str(content)


_PLAN_MARKERS = ("# ✈️", "## 🧠 Trip Summary", "# Your Personalized Trip Plan")

logger = logging.getLogger("yatra.graph")


def assemble_reply(messages) -> str:
    """Join AI text produced for the latest human turn into one reply.

    A plan may be split across multiple AIMessages when the model interleaves
    a tool call mid-document (header in one message, continuation in the
    next). If the final text is a standalone plan or conversational reply,
    it is returned alone; otherwise it is merged onto the most recent
    message that opened the plan.
    """
    last_human = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human = i
            break
    segment = messages[last_human + 1 :] if last_human >= 0 else messages

    ai_texts = [
        _msg_text(m)
        for m in segment
        if isinstance(m, AIMessage) and _msg_text(m).strip()
    ]
    if not ai_texts:
        return ""

    last = ai_texts[-1]
    if any(marker in last for marker in _PLAN_MARKERS):
        return last

    for j in range(len(ai_texts) - 1, -1, -1):
        if any(marker in ai_texts[j] for marker in _PLAN_MARKERS):
            return "\n".join(ai_texts[j:])
    return last


def _latest_ai_text(state) -> str:
    return assemble_reply(state.get("messages", []))


# ── Node factories ───────────────────────────────────────────────────────

def _with_retry(runnable):
    """Retry transient LLM failures (e.g. free-tier 429s) with backoff."""
    return runnable.with_retry(
        stop_after_attempt=4,
        wait_exponential_jitter=True,
    )


def create_extract_node():
    models = get_llm_models("light")
    extractor = _with_retry(
        models[0].with_structured_output(TravelRequirements).with_fallbacks(
            [m.with_structured_output(TravelRequirements) for m in models[1:]]
        )
    )

    async def extract_requirements(state):
        user_message = _latest_human_message(state)
        previous = state.get("requirements") or {}
        prefs = state.get("profile_prefs")

        prompt = EXTRACTION_PROMPT.replace(
            "{user_message}", user_message
        ).replace(
            "{previous_requirements}",
            json.dumps(previous, indent=2) if previous else "none",
        ).replace(
            "{profile_prefs}",
            json.dumps(prefs, indent=2, default=str) if prefs else "none",
        )

        try:
            req: TravelRequirements = await extractor.ainvoke(prompt)
        except Exception:
            # Extraction failure must not break the conversation — degrade
            # to planning directly on the raw conversation.
            return {"requirements": previous, "needs_clarification": False}

        req_dict = req.model_dump()

        # Clarify only for the initial request; a replan turn (existing
        # requirements) resolves ambiguity against the current plan.
        logger.info(
            "node=extract plan_request=%s clarify=%s dest=%s budget=%s",
            req.is_plan_request,
            req.needs_clarification,
            req_dict.get("destination"),
            req_dict.get("budget_total"),
        )

        if (
            req.needs_clarification
            and req.clarifying_question
            and req.is_plan_request
        ):
            return {
                "requirements": req_dict,
                "needs_clarification": True,
                "messages": [AIMessage(content=req.clarifying_question)],
            }

        return {"requirements": req_dict, "needs_clarification": False}

    return extract_requirements


def create_planner_node(tools):
    models = get_llm_models("planner")
    llm = _with_retry(
        models[0].bind_tools(tools).with_fallbacks(
            [m.bind_tools(tools) for m in models[1:]]
        )
    )

    async def planner(state):
        requirements = state.get("requirements") or {}
        prefs = state.get("profile_prefs")
        system = SYSTEM_PROMPT.replace(
            "{requirements_json}", json.dumps(requirements, indent=2)
        ).replace(
            "{profile_prefs}",
            json.dumps(prefs, indent=2, default=str) if prefs else "none",
        )

        messages = state.get("messages", [])
        invoke_messages: list[Any] = [SystemMessage(content=system), *messages]

        feedback = state.get("validation_feedback")
        if feedback:
            invoke_messages.append(
                HumanMessage(
                    content=(
                        "Your previous draft failed verification. "
                        f"Fix these issues:\n{feedback}\n\n"
                        "Output the COMPLETE corrected plan in the required "
                        "format — every section, start to finish."
                    )
                )
            )

        response = await llm.ainvoke(invoke_messages)

        # Some models occasionally return an empty final message (no text,
        # no tool calls). Re-invoke once before accepting a dead end.
        if not getattr(response, "tool_calls", None) and not _msg_text(
            response
        ).strip():
            logger.warning("node=planner empty response — retrying once")
            response = await llm.ainvoke(invoke_messages)

        calls = [tc["name"] for tc in getattr(response, "tool_calls", None) or []]
        logger.info(
            "node=planner tool_calls=%s reply_chars=%d",
            calls,
            len(_msg_text(response)),
        )

        update: dict[str, Any] = {"messages": [response]}
        if not getattr(response, "tool_calls", None):
            # A final (non-tool) response was drafted — clear feedback.
            update["validation_feedback"] = None
        return update

    return planner


def create_verify_node(max_loops: int):
    models = get_llm_models("light")
    verifier = _with_retry(
        models[0].with_structured_output(PlanVerification).with_fallbacks(
            [m.with_structured_output(PlanVerification) for m in models[1:]]
        )
    )

    async def verify(state):
        plan = _latest_ai_text(state)
        requirements = state.get("requirements") or {}
        verify_count = state.get("verify_count", 0) + 1

        if not plan or not requirements.get("is_plan_request", True):
            return {"verify_count": verify_count}

        budget = requirements.get("budget_total")
        issues: list[str] = []

        try:
            result: PlanVerification = await verifier.ainvoke(
                VERIFICATION_PROMPT.replace(
                    "{requirements}", json.dumps(requirements, indent=2)
                ).replace("{plan}", plan)
            )
            issues.extend(result.issues)
            claimed = result.claimed_total_cost
        except Exception:
            claimed = None

        # Deterministic budget check — never silently pass an over-budget plan.
        if budget is not None and claimed is not None and claimed > budget:
            issues.append(
                f"Stated total {claimed:g} exceeds the hard budget of "
                f"{budget:g}. Cut the largest cost drivers and recalculate."
            )

        if issues and verify_count <= max_loops:
            logger.info(
                "node=verify FAILED attempt=%d issues=%s", verify_count, issues
            )
            return {
                "verify_count": verify_count,
                "validation_feedback": "\n".join(f"- {i}" for i in issues),
            }
        logger.info("node=verify passed attempt=%d", verify_count)
        return {"verify_count": verify_count, "validation_feedback": None}

    return verify
