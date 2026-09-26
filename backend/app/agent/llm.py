"""LLM factory with per-role models and provider fallback chains.

Gemini free tier quotas are per-model per-day, so the planner (quality
critical) and the lightweight extract/verify stages use different models —
and each stage carries a fallback chain across models so an exhausted quota
or a temporary overload degrades gracefully instead of erroring.
"""

from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from app.config import get_settings


def _gemini(model: str) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
    )


def _groq() -> BaseChatModel:
    settings = get_settings()
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
    )


def get_llm_models(role: str = "planner") -> list[BaseChatModel]:
    """Return [primary, *fallbacks] chat models for the given role.

    role="planner"  — the itinerary-writing model (best quality)
    role="light"    — extraction/verification calls (cheap, separate quota)
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        primary_model = (
            settings.gemini_model
            if role == "planner"
            else settings.gemini_light_model
        )
        chain = [primary_model, *settings.gemini_fallback_models_list]
        seen = set()
        models = [
            _gemini(m) for m in chain if not (m in seen or seen.add(m))
        ]
        return models

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")
        return [_groq()]

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def get_llm(role: str = "planner") -> BaseChatModel:
    """Primary model for the role (kept for single-model call sites)."""
    return get_llm_models(role)[0]
