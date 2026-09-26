"""Yatra AI backend — FastAPI entry point."""

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.routes import router as agent_router
from app.auth.routes import router as auth_router
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("yatra.api")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_secrets()

    app = FastAPI(title="Yatra AI API", version="1.0.0")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Attach a request id + structured access log to every request."""
        request_id = uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.time()
        response = await call_next(request)
        logger.info(
            "request_id=%s %s %s -> %s (%.0fms)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            (time.time() - start) * 1000,
        )
        response.headers["X-Request-Id"] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        """Never leak stack traces / internals to clients."""
        logger.exception(
            "unhandled error request_id=%s path=%s",
            getattr(request.state, "request_id", "-"),
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

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
