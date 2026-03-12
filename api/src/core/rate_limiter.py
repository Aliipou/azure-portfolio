"""Token-bucket rate limiter backed by Redis (in-memory fallback for dev)."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from src.config import settings
from src.core.auth import get_current_user
from src.models.schemas import UserClaims


class InMemoryTokenBucket:
    """Simple in-memory rate limiter for development."""

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"tokens": settings.rate_limit_per_minute, "last_refill": time.time()}
        )

    def is_allowed(self, key: str, limit: int = 60) -> tuple[bool, int, int]:
        bucket = self._buckets[key]
        now = time.time()
        elapsed = now - bucket["last_refill"]
        refill = elapsed * (limit / 60)
        bucket["tokens"] = min(limit, bucket["tokens"] + refill)
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            remaining = int(bucket["tokens"])
            reset = int(now + (1 / (limit / 60)))
            return True, remaining, reset
        reset = int(bucket["last_refill"] + 60)
        return False, 0, reset


_in_memory_limiter = InMemoryTokenBucket()


async def rate_limit(
    request: Request,
    user: UserClaims = Depends(get_current_user),
) -> None:
    """FastAPI dependency: enforce per-user rate limit."""
    key = f"rl:{user.sub}"
    limit = settings.rate_limit_per_minute

    allowed, remaining, reset_at = _in_memory_limiter.is_allowed(key, limit)

    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = reset_at

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry after the reset time.",
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(max(0, reset_at - int(time.time()))),
            },
        )
