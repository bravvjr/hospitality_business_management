"""Lightweight in-memory rate limiting for sensitive endpoints (ADR-003).

A per-process sliding-window limiter keyed by endpoint scope + client IP. This is
intentionally simple for the MVP; for multi-instance deployments swap the store
for a shared backend (e.g. Redis) behind the same `RateLimiter` interface.
"""
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, max_requests: int, window_seconds: float) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        hits = self._hits[key]
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


_limiter = RateLimiter()


def get_limiter() -> RateLimiter:
    return _limiter


def rate_limit(scope: str):
    """Build a dependency that limits requests for a named scope by client IP."""

    async def _dependency(
        request: Request,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        if not settings.rate_limit_enabled:
            return
        client_ip = request.client.host if request.client else "unknown"
        key = f"{scope}:{client_ip}"
        allowed = _limiter.allow(
            key,
            max_requests=settings.auth_rate_limit_max,
            window_seconds=settings.auth_rate_limit_window_seconds,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, please slow down.",
                headers={"Retry-After": str(settings.auth_rate_limit_window_seconds)},
            )

    return _dependency
