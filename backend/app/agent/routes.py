"""Agent chat endpoint.

Authenticated users get full threads scoped by their id. Guests (the
"skip registration" path) may chat too — rate-limited per client IP and
threaded under a guest namespace. Only saving trips requires an account.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from app.agent.service import run_agent_turn
from app.auth.deps import get_optional_user
from app.auth.ratelimit import guest_chat_limiter

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
def chat(
    body: ChatRequest,
    request: Request,
    user=Depends(get_optional_user),
):
    thread_id = body.thread_id or uuid4().hex

    if user is not None:
        owner = str(user.id)
        guest = False
    else:
        ip = request.client.host if request.client else "unknown"
        if not guest_chat_limiter.allow(f"guest-chat:{ip}"):
            raise HTTPException(
                429,
                "Guest limit reached. Create a free account to keep planning.",
            )
        owner = f"guest:{ip}"
        guest = True

    try:
        result = run_agent_turn(
            user_id=owner, thread_id=thread_id, message=body.message
        )
        result["guest"] = guest
        return result
    except Exception as exc:
        raise HTTPException(500, f"Agent error: {exc}")
