"""Agent chat endpoint — the only AI surface, auth-protected."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.agent.service import run_agent_turn
from app.auth.deps import get_current_user

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
def chat(body: ChatRequest, user=Depends(get_current_user)):
    thread_id = body.thread_id or uuid4().hex
    try:
        return run_agent_turn(
            user_id=str(user.id), thread_id=thread_id, message=body.message
        )
    except Exception as exc:
        raise HTTPException(500, f"Agent error: {exc}")
