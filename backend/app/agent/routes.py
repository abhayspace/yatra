"""Agent chat endpoint.

Authenticated users get full threads scoped by their id. Guests (the
"skip registration" path) may chat too — rate-limited per client IP and
threaded under a guest namespace. Only saving trips requires an account.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from app.agent.service import run_agent_turn
from app.auth.deps import get_optional_user
from app.auth.ratelimit import guest_chat_limiter

logger = logging.getLogger("yatra.agent")

router = APIRouter(prefix="/api", tags=["agent"])


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None

    @field_validator("message")
    @classmethod
    def message_ok(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        if len(v) > 4000:
            raise ValueError("Message too long (max 4000 chars)")
        return v


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    user=Depends(get_optional_user),
):
    thread_id = body.thread_id or uuid4().hex

    if user is not None:
        owner = str(user.id)
        guest = False
    else:
        # Behind nginx+Cloudflare the direct peer is always 127.0.0.1.
        # CF-Connecting-IP is set by Cloudflare from the real TCP peer and
        # overwrites any client-spoofed value; X-Forwarded-For's first hop
        # is client-controllable, so it is the weaker fallback.
        ip = (
            request.headers.get("cf-connecting-ip")
            or request.headers.get("x-real-ip")
            or (request.client.host if request.client else "unknown")
        )
        if not guest_chat_limiter.allow(f"guest-chat:{ip}"):
            raise HTTPException(
                429,
                "Guest limit reached. Create a free account to keep planning.",
            )
        owner = f"guest:{ip}"
        guest = True

    try:
        result = await run_agent_turn(
            user_id=owner, thread_id=thread_id, message=body.message
        )
        result["guest"] = guest
        return result
    except Exception as exc:
        logger.exception("agent turn failed (thread=%s owner=%s)", thread_id, owner)
        raise HTTPException(
            500, "The agent hit an error generating a response. Please retry."
        ) from exc
