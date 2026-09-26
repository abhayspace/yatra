"""Supabase clients.

Two clients are exposed:

- ``get_service_client()`` — secret/service key. Server-side ONLY. Used for
  admin operations (creating auth users, OTP bookkeeping, username lookups).
  Never expose this key or its responses containing secrets to the client.

- ``get_anon_client()`` — publishable key. Used for user-level auth calls
  such as ``sign_in_with_password`` so issued sessions are ordinary user
  sessions that Row Level Security applies to.

The frontend uses the publishable key directly for data access; RLS policies
in ``schema.sql`` enforce per-user isolation there.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_service_client() -> Client:
    settings = get_settings()
    if not settings.supabase_secret_key:
        raise RuntimeError("SUPABASE_SECRET_KEY is not configured")
    return create_client(settings.supabase_url, settings.supabase_secret_key)


@lru_cache
def get_anon_client() -> Client:
    settings = get_settings()
    if not settings.supabase_publishable_key:
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY is not configured")
    return create_client(settings.supabase_url, settings.supabase_publishable_key)


def get_user_from_token(access_token: str):
    """Validate a Supabase access token and return the auth user (or None)."""
    try:
        resp = get_service_client().auth.get_user(access_token)
    except Exception:
        return None
    return getattr(resp, "user", None)
