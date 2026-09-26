"""Authentication routes implementing the Yatra AI signup/login flow.

Flow (per spec):
  1. POST /register        — full name + email → OTP emailed via Resend
  2. POST /verify-otp      — OTP check → short-lived setup token
  3. POST /setup-credentials — username + password → Supabase Auth account
  4. POST /login           — username + password → Supabase session
  5. POST /forgot-password + /reset-password — OTP-based recovery

Passwords are never stored by us — hashing is delegated to Supabase Auth
(GoTrue, bcrypt). OTPs are stored hashed with per-record salts.
"""

import re
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

from app.auth.deps import get_current_user
from app.auth.otp import issue_otp, verify_otp
from app.auth.ratelimit import login_limiter, otp_limiter
from app.config import get_settings
from app.db.supabase import get_anon_client, get_service_client
from app.email.service import send_password_reset_otp, send_verification_otp

router = APIRouter(prefix="/api/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


# ── Schemas ──────────────────────────────────────────────────────────────

def _password_check(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must contain letters and digits")
    return v


class RegisterRequest(BaseModel):
    username: str
    full_name: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("username")
    @classmethod
    def username_ok(cls, v: str) -> str:
        if not USERNAME_RE.fullmatch(v):
            raise ValueError(
                "Username must be 3–20 chars: letters, digits, underscore"
            )
        return v

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        v = v.strip()
        if not (2 <= len(v) <= 100):
            raise ValueError("Full name must be 2–100 characters")
        return v

    @field_validator("password")
    @classmethod
    def pw_ok(cls, v: str) -> str:
        return _password_check(v)


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str

    @field_validator("otp")
    @classmethod
    def otp_ok(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v.strip()):
            raise ValueError("OTP must be a 6-digit code")
        return v.strip()


class ResendOtpRequest(BaseModel):
    email: EmailStr
    purpose: str = "verify"

    @field_validator("purpose")
    @classmethod
    def purpose_ok(cls, v: str) -> str:
        if v not in {"verify", "reset"}:
            raise ValueError("Invalid purpose")
        return v


class SetupCredentialsRequest(BaseModel):
    """Username is carried inside the verified setup token, not the body."""

    setup_token: str
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        return _password_check(v)


class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        return _password_check(v)


# ── Helpers ──────────────────────────────────────────────────────────────

def _issue_setup_token(
    email: str, full_name: str | None = None, username: str | None = None
) -> str:
    settings = get_settings()
    payload = {
        "sub": email,
        "purpose": "setup",
        "full_name": full_name or "",
        "username": username or "",
        "exp": datetime.now(UTC)
        + timedelta(seconds=settings.setup_token_ttl_seconds),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.backend_jwt_secret, algorithm="HS256")


def _read_setup_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.backend_jwt_secret, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        raise HTTPException(
            400, "Setup session is invalid or expired. Start over."
        ) from None
    if payload.get("purpose") != "setup":
        raise HTTPException(400, "Invalid setup token")
    return payload


def _find_auth_user_by_email(email: str):
    """Look up a Supabase auth user by email (admin/service context)."""
    client = get_service_client()
    page = 1
    while page <= 20:  # cap pages for safety
        resp = client.auth.admin.list_users(page=page, per_page=100)
        users = resp if isinstance(resp, list) else getattr(resp, "users", [])
        for u in users:
            if (u.email or "").lower() == email.lower():
                return u
        if len(users) < 100:
            break
        page += 1
    return None


def _username_taken(username: str) -> bool:
    client = get_service_client()
    res = (
        client.table("users")
        .select("id")
        .ilike("username", username)
        .limit(1)
        .execute()
    )
    return bool(res.data)


def _email_registered(email: str) -> bool:
    client = get_service_client()
    res = (
        client.table("users")
        .select("id")
        .ilike("email", email)
        .limit(1)
        .execute()
    )
    return bool(res.data) or _find_auth_user_by_email(email) is not None


def _session_payload(auth_response) -> dict:
    session = auth_response.session
    user = auth_response.user
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": (user.user_metadata or {}).get("username"),
            "full_name": (user.user_metadata or {}).get("full_name"),
        },
    }


# ── Routes ───────────────────────────────────────────────────────────────

@router.post("/register")
def register(body: RegisterRequest):
    """Step 1 — username, name, email + password; then email OTP."""
    email = body.email.lower()

    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    if _email_registered(email):
        raise HTTPException(409, "An account with this email already exists.")
    if _username_taken(body.username):
        raise HTTPException(409, "Username is already taken.")

    if not otp_limiter.allow(f"register:{email}"):
        raise HTTPException(429, "Too many requests. Try again in a minute.")

    otp, error = issue_otp(email, purpose="verify")
    if error:
        raise HTTPException(429, error)

    # Stash name+username until verification completes; the setup token
    # minted after OTP verification carries them into account creation.
    # The password is never stored — the client re-sends it at setup time.
    get_service_client().table("pending_registrations").upsert(
        {
            "email": email,
            "full_name": body.full_name,
            "username": body.username,
        }
    ).execute()

    sent = send_verification_otp(email, otp)

    settings = get_settings()
    if not sent and not settings.debug:
        raise HTTPException(
            503, "Email delivery failed — please try again shortly."
        )
    response = {
        "status": "otp_sent",
        "message": (
            f"Verification code sent to {email}"
            if sent
            else f"Email delivery unavailable — code logged server-side for {email}"
        ),
        "expires_in": settings.otp_ttl_seconds,
    }
    return response


@router.post("/resend-otp")
def resend_otp(body: ResendOtpRequest):
    email = body.email.lower()

    if not otp_limiter.allow(f"resend:{email}"):
        raise HTTPException(429, "Too many requests. Try again in a minute.")

    otp, error = issue_otp(email, purpose=body.purpose)
    if error:
        raise HTTPException(429, error)

    if body.purpose == "verify":
        sent = send_verification_otp(email, otp)
    else:
        sent = send_password_reset_otp(email, otp)

    settings = get_settings()
    if not sent and not settings.debug:
        raise HTTPException(
            503, "Email delivery failed — please try again shortly."
        )
    return {"status": "otp_sent", "expires_in": settings.otp_ttl_seconds}


@router.post("/verify-otp")
def verify_otp_route(body: VerifyOtpRequest):
    """Step 1b — verify the emailed OTP, return a setup token."""
    email = body.email.lower()

    ok, error = verify_otp(email, body.otp, purpose="verify")
    if not ok:
        if error == "expired":
            raise HTTPException(
                410, "Code expired. Request a new verification code."
            )
        raise HTTPException(400, error or "Verification failed")

    service = get_service_client()
    pending = (
        service.table("pending_registrations")
        .select("full_name, username")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    full_name = pending.data[0]["full_name"] if pending.data else ""
    username = pending.data[0].get("username", "") if pending.data else ""
    service.table("pending_registrations").delete().eq("email", email).execute()

    return {
        "status": "verified",
        "setup_token": _issue_setup_token(email, full_name, username),
    }


@router.post("/setup-credentials")
def setup_credentials(body: SetupCredentialsRequest):
    """Step 2 — create username + password; activates the account."""
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match")

    payload = _read_setup_token(body.setup_token)
    email = payload["sub"].lower()
    full_name = payload.get("full_name", "")
    username = payload.get("username", "")

    if not username or not USERNAME_RE.fullmatch(username):
        raise HTTPException(400, "Setup token is missing a valid username")
    if _email_registered(email):
        raise HTTPException(409, "Account already exists. Please log in.")
    if _username_taken(username):
        raise HTTPException(409, "Username is already taken.")

    service = get_service_client()
    created = service.auth.admin.create_user(
        {
            "email": email,
            "password": body.password,
            "email_confirm": True,
            "user_metadata": {
                "username": username,
                "full_name": full_name,
            },
        }
    )
    user = created.user
    if user is None:
        raise HTTPException(500, "Failed to create account")

    # Public profile + default travel profile (service role; RLS-safe writes).
    now = datetime.now(UTC).isoformat()
    service.table("users").insert(
        {
            "id": user.id,
            "email": email,
            "username": username,
            "full_name": full_name,
            "created_at": now,
            "updated_at": now,
        }
    ).execute()
    service.table("travel_profiles").insert({"user_id": user.id}).execute()

    # Sign in immediately so the user lands on the dashboard.
    anon = get_anon_client()
    session = anon.auth.sign_in_with_password(
        {"email": email, "password": body.password}
    )
    return {"status": "created", **_session_payload(session)}


@router.post("/login")
def login(body: LoginRequest):
    """Step 3 — username + password login (OTP not required)."""
    if not login_limiter.allow(f"login:{body.username.lower()}"):
        raise HTTPException(429, "Too many login attempts. Try again shortly.")

    # Resolve username → email via the profile table (service-side lookup).
    service = get_service_client()
    res = (
        service.table("users")
        .select("email")
        .ilike("username", body.username.strip())
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(401, "Invalid username or password")

    email = res.data[0]["email"]

    anon = get_anon_client()
    try:
        session = anon.auth.sign_in_with_password(
            {"email": email, "password": body.password}
        )
    except Exception:
        raise HTTPException(401, "Invalid username or password") from None

    return _session_payload(session)


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest):
    """Start password recovery — email a reset OTP if the account exists."""
    email = body.email.lower()

    if not otp_limiter.allow(f"forgot:{email}"):
        raise HTTPException(429, "Too many requests. Try again in a minute.")

    # Always answer identically to avoid account enumeration.
    if _email_registered(email):
        otp, error = issue_otp(email, purpose="reset")
        if error:
            raise HTTPException(429, error)
        send_password_reset_otp(email, otp)

    return {
        "status": "ok",
        "message": "If the email is registered, a reset code has been sent.",
    }


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest):
    """Verify reset OTP and set a new password."""
    email = body.email.lower()

    ok, error = verify_otp(email, body.otp.strip(), purpose="reset")
    if not ok:
        if error == "expired":
            raise HTTPException(410, "Code expired. Request a new reset code.")
        raise HTTPException(400, error or "Verification failed")

    user = _find_auth_user_by_email(email)
    if user is None:
        raise HTTPException(404, "Account not found")

    get_service_client().auth.admin.update_user_by_id(
        user.id, {"password": body.new_password}
    )
    return {"status": "password_updated"}


@router.get("/me")
def me(user=Depends(get_current_user)):
    """Return the authenticated user's profile."""
    service = get_service_client()
    res = (
        service.table("users")
        .select("*")
        .eq("id", user.id)
        .limit(1)
        .execute()
    )
    profile = res.data[0] if res.data else None
    return {
        "id": user.id,
        "email": user.email,
        "profile": profile,
    }
