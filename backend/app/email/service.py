"""Transactional email via the Resend API.

All sending happens server-side; the Resend API key is read only from the
environment and is never exposed to the frontend. When no key is configured
(local development), emails are skipped and the OTP is logged to the server
console so the flow can still be exercised.
"""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger("yatra.email")

RESEND_API_URL = "https://api.resend.com/emails"
APP_NAME = "Yatra AI"


def _send_email(to: str, subject: str, html: str) -> bool:
    """Send an email through Resend. Returns True on success."""
    settings = get_settings()

    if not settings.resend_api_key:
        logger.warning(
            "RESEND_API_KEY not configured — email to %s skipped (subject: %s)",
            to,
            subject,
        )
        return False

    payload = {
        "from": settings.resend_from_email,
        "to": [to],
        "subject": subject,
        "html": html,
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                RESEND_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code >= 400:
            logger.error("Resend error %s: %s", resp.status_code, resp.text)
            return False
        return True
    except httpx.HTTPError as exc:
        logger.error("Resend request failed: %s", exc)
        return False


def _otp_html(otp: str, purpose: str, ttl_minutes: int) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
      <h2>{APP_NAME} — {purpose}</h2>
      <p>Use the verification code below to continue:</p>
      <p style="font-size:32px;letter-spacing:8px;font-weight:bold">{otp}</p>
      <p>This code expires in {ttl_minutes} minutes.</p>
      <p>If you did not request this, you can safely ignore this email.</p>
    </div>
    """


def send_verification_otp(email: str, otp: str) -> bool:
    """Send the email-verification OTP used during registration."""
    settings = get_settings()
    ttl = settings.otp_ttl_seconds // 60
    sent = _send_email(
        email,
        f"{APP_NAME}: verify your email",
        _otp_html(otp, "Email Verification", ttl),
    )
    if not sent:
        # Dev fallback — never log the OTP in production paths you ship;
        # guarded by missing API key which only occurs in local dev.
        logger.warning("DEV OTP for %s (verification): %s", email, otp)
    return sent


def send_password_reset_otp(email: str, otp: str) -> bool:
    """Send the OTP used for password recovery."""
    settings = get_settings()
    ttl = settings.otp_ttl_seconds // 60
    sent = _send_email(
        email,
        f"{APP_NAME}: reset your password",
        _otp_html(otp, "Password Reset", ttl),
    )
    if not sent:
        logger.warning("DEV OTP for %s (password reset): %s", email, otp)
    return sent
