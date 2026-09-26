"""Simple in-memory fixed-window rate limiter.

Sufficient for a single-process demo deployment. For multi-worker production
use, swap for a Redis/Supabase-backed limiter.
"""

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        hits = [t for t in self._hits[key] if t > window_start]
        self._hits[key] = hits
        if len(hits) >= self.max_attempts:
            return False
        hits.append(now)
        return True


# Login: 5 attempts per minute per username/IP-ish key
login_limiter = RateLimiter(max_attempts=5, window_seconds=60)

# OTP endpoints: 3 requests per minute per email
otp_limiter = RateLimiter(max_attempts=3, window_seconds=60)

# Guest (unauthenticated) chat: 15 messages per hour per IP
guest_chat_limiter = RateLimiter(max_attempts=15, window_seconds=3600)
