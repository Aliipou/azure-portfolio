"""Tests for rate limiting."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.core.rate_limiter import InMemoryTokenBucket


class TestInMemoryTokenBucket:
    def test_first_request_allowed(self) -> None:
        bucket = InMemoryTokenBucket()
        allowed, remaining, reset = bucket.is_allowed("user-1", limit=10)
        assert allowed is True
        assert remaining == 9

    def test_requests_depleted_returns_denied(self) -> None:
        bucket = InMemoryTokenBucket()
        for _ in range(10):
            bucket.is_allowed("user-2", limit=10)
        allowed, remaining, _ = bucket.is_allowed("user-2", limit=10)
        assert allowed is False
        assert remaining == 0

    def test_different_users_have_separate_buckets(self) -> None:
        bucket = InMemoryTokenBucket()
        for _ in range(10):
            bucket.is_allowed("user-a", limit=10)
        # user-b should still have tokens
        allowed_b, _, _ = bucket.is_allowed("user-b", limit=10)
        assert allowed_b is True

    def test_remaining_decrements(self) -> None:
        bucket = InMemoryTokenBucket()
        _, r1, _ = bucket.is_allowed("user-c", limit=5)
        _, r2, _ = bucket.is_allowed("user-c", limit=5)
        assert r2 < r1
