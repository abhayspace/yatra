"""Trajectory evaluation — runs the REAL agent graph end-to-end.

Unlike unit tests that mock the LLM, these evals invoke the compiled graph
with live models and inspect the resulting message trajectory: which tools
were called, whether the reply contains the required sections, whether the
claimed budget stays under the user's hard limit, and whether adversarial
inputs are resisted.

Requires a working LLM provider key (GEMINI_API_KEY or GROQ_API_KEY).
"""

import asyncio
import json
import re
from pathlib import Path
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.checkpoint import ensure_checkpointer_setup
from app.agent.graph import get_graph
from app.agent.nodes import assemble_reply
from app.config import get_settings

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "travel_cases.json"


def load_cases():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _tool_names(messages):
    names = []
    for m in messages:
        if isinstance(m, AIMessage):
            for tc in getattr(m, "tool_calls", None) or []:
                names.append(tc["name"])
    return names


def _claimed_total(reply: str) -> float | None:
    """Pull the largest ₹/Rs/INR figure near a TOTAL row from the plan."""
    candidates = re.findall(r"(?:TOTAL|total)[^0-9₹]*[₹Rs\.]*\s*([\d,]+)", reply)
    if candidates:
        return float(candidates[-1].replace(",", ""))
    return None


def eval_trajectory(case: dict) -> dict:
    return asyncio.run(_eval_trajectory(case))


async def _eval_trajectory(case: dict) -> dict:
    graph = get_graph()
    await ensure_checkpointer_setup()
    settings = get_settings()
    config = {
        "configurable": {"thread_id": f"eval-{uuid4()}"},
        "recursion_limit": settings.agent_recursion_limit,
    }

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=case["input"])]}, config=config
    )
    messages = result["messages"]
    reply = assemble_reply(messages)
    tools_used = _tool_names(messages)

    checks = {}
    failures = []

    if case["type"] == "trajectory":
        # Tool grounding: at least one expected tool must have been called.
        hit = any(t in tools_used for t in case["expect_tools_any"])
        checks["tool_used"] = hit
        if not hit:
            failures.append(
                f"none of expected tools called (wanted one of "
                f"{case['expect_tools_any']}, got {tools_used})"
            )

        # Required plan sections.
        missing = [s for s in case["expect_sections"] if s not in reply]
        checks["sections_present"] = not missing
        if missing:
            failures.append(f"missing sections: {missing}")

        # Budget: claimed total must not exceed the hard limit.
        total = _claimed_total(reply)
        if total is not None and total > case["max_claimed_total"]:
            checks["budget_respected"] = False
            failures.append(
                f"claimed total {total} exceeds {case['max_claimed_total']}"
            )
        else:
            checks["budget_respected"] = True

    elif case["type"] == "replan":
        # Second turn must explain WHAT CHANGED / WHY / NEW COST.
        result2 = await graph.ainvoke(
            {"messages": [HumanMessage(content=case["followup"])]},
            config=config,
        )
        reply = assemble_reply(result2["messages"])
        for token in case["expect_regex"]:
            if token not in reply:
                checks[f"replan_marker_{token}"] = False
                failures.append(f"replan reply missing '{token}'")
            else:
                checks[f"replan_marker_{token}"] = True
        total = _claimed_total(reply)
        if total is not None and total > case["max_claimed_total"]:
            failures.append(f"new total {total} exceeds {case['max_claimed_total']}")
            checks["budget_respected"] = False
        else:
            checks["budget_respected"] = True

    elif case["type"] == "safety":
        lowered = reply.lower()
        for banned in case["must_not_contain"]:
            if banned.lower() in lowered:
                checks[f"no_{banned}"] = False
                failures.append(f"reply leaked/forbidden content: {banned}")
            else:
                checks[f"no_{banned}"] = True
        for s in case["expect_sections"]:
            if s not in reply:
                checks["still_helpful"] = False
                failures.append(f"agent did not still answer: missing '{s}'")
                break
        else:
            checks["still_helpful"] = True

    elif case["type"] == "edge":
        clarified = bool(result.get("needs_clarification"))
        assumed = bool(
            (result.get("requirements") or {}).get("assumptions")
        )
        checks["handled"] = clarified or assumed or bool(reply.strip())
        if not checks["handled"]:
            failures.append("no clarification, assumptions, or reply")

    elif case["type"] == "chat":
        for s in case["expect_sections_absent"]:
            if s in reply:
                checks["no_plan_sections"] = False
                failures.append(f"unexpected plan section: {s}")
                break
        else:
            checks["no_plan_sections"] = True
        checks["answered"] = bool(reply.strip())
        if not reply.strip():
            failures.append("empty reply")

    return {
        "id": case["id"],
        "name": case["name"],
        "tools_used": tools_used,
        "checks": checks,
        "passed": not failures,
        "failures": failures,
        "reply_chars": len(reply),
    }


if __name__ == "__main__":
    cases = [c for c in load_cases() if c["type"] != "judge"]
    for c in cases:
        print(f"\n=== {c['id']} {c['name']}")
        r = eval_trajectory(c)
        print(f"  tools: {r['tools_used']}")
        print(f"  {'PASS' if r['passed'] else 'FAIL'} — {r['failures'] or 'ok'}")
