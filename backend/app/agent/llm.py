from langchain_groq import ChatGroq

from app.config import get_settings


def get_llm():
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")
        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=0,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
