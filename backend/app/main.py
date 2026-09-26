"""Yatra AI backend — FastAPI entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.routes import router as agent_router
from app.auth.routes import router as auth_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Yatra AI API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(agent_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "yatra-ai"}

    return app


app = create_app()
