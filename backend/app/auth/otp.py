"""OTP lifecycle stored in the ``email_otps`` Supabase table.

OTPs are stored hashed (SHA-256 with a per-record salt) and compared with a
constant-time digest check. The table is written only through the service
client and has RLS enabled with no public policies, so it is unreachable via
the publishable key.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.config import get_settings
from app.db.supabase import get_service_client


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(otp: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{otp}".encode()).hexdigest()


def issue_otp(email: str, purpose: str) -> tuple[str, str | None]:
    """Create and return (otp, error). Enforces resend cooldown."""
    settings = get_settings()
    client = get_service_client()

    # Cooldown: reject if a code for this email+purpose was issued recently.
    cooldown_start = (
        _now() - timedelta(seconds=settings.otp_resend_cooldown_seconds)
    ).isoformat()

    recent = (
        client.table("email_otps")
        .select("id, created_at")
        .eq("email", email)
        .eq("purpose", purpose)
        .gte("created_at", cooldown_start)
        .execute()
    )
    if recent.data:
        wait = settings.otp_resend_cooldown_seconds
        return "", f"Please wait {wait}s before requesting a new code."

    # Invalidate previous OTPs for this email+purpose.
    client.table("email_otps").delete().eq("email", email).eq(
        "purpose", purpose
    ).execute()

    otp = f"{secrets.randbelow(1_000_000):06d}"
    salt = uuid4().hex
    expires_at = _now() + timedelta(seconds=settings.otp_ttl_seconds)

    client.table("email_otps").insert(
        {
            "email": email,
            "purpose": purpose,
            "otp_hash": _hash(otp, salt),
            "salt": salt,
            "expires_at": expires_at.isoformat(),
            "attempts": 0,
        }
    ).execute()

    return otp, None


def verify_otp(email: str, otp: str, purpose: str) -> tuple[bool, str | None]:
    """Verify an OTP. Returns (ok, error_message)."""
    settings = get_settings()
    client = get_service_client()

    rows = (
        client.table("email_otps")
        .select("*")
        .eq("email", email)
        .eq("purpose", purpose)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not rows.data:
        return False, "No verification code was requested for this email."

    record = rows.data[0]

    if datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00")) < _now():
        return False, "expired"

    if record["attempts"] >= settings.otp_max_attempts:
        return False, "Too many incorrect attempts. Request a new code."

    candidate = _hash(otp, record["salt"])
    if not hmac.compare_digest(candidate, record["otp_hash"]):
        client.table("email_otps").update(
            {"attempts": record["attempts"] + 1}
        ).eq("id", record["id"]).execute()
        return False, "Incorrect verification code."

    # Success — consume the OTP.
    client.table("email_otps").delete().eq("id", record["id"]).execute()
    return True, None
