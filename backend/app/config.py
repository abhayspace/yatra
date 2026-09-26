"""Centralized application settings loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwks_url: str = ""

    # Resend email
    resend_api_key: str = ""
    resend_from_email: str = "Yatra AI <onboarding@resend.dev>"

    # LLM
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_light_model: str = "gemini-3.5-flash-lite"
    # Comma-separated fallbacks tried when a model's quota/health fails.
    gemini_fallback_models: str = "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-flash-lite-latest"

    # Backend
    # Required in non-debug mode — no insecure default shipped.
    backend_jwt_secret: str = ""
    backend_cors_origins: str = "http://localhost:5173"
    sqlite_db_path: str = "data/checkpoints.sqlite"
    debug: bool = False

    # Auth policy
    otp_ttl_seconds: int = 600          # 10 minutes
    otp_resend_cooldown_seconds: int = 60
    otp_max_attempts: int = 5
    setup_token_ttl_seconds: int = 900  # 15 minutes to finish signup

    # Agent
    agent_recursion_limit: int = 25
    agent_max_verify_loops: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def validate_secrets(self) -> None:
        """Fail fast on missing secrets outside debug mode."""
        if not self.debug and not self.backend_jwt_secret:
            raise RuntimeError(
                "BACKEND_JWT_SECRET must be set when DEBUG is disabled"
            )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @property
    def gemini_fallback_models_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
