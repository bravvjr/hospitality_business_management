"""Rate limiting for sensitive endpoints (ADR-003).

Supports an in-memory backend (default) and an optional Redis backend for
multi-instance deployments. Tests use the memory backend.
"""
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings


class RateLimitBackend(ABC):
    @abstractmethod
    def allow(self, key: str, *, max_requests: int, window_seconds: float) -> bool:
        """Return True when the request is within the configured limit."""

    @abstractmethod
    def reset(self) -> None:
        """Clear counters (used by tests)."""


class MemoryRateLimitBackend(RateLimitBackend):
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


class RedisRateLimitBackend(RateLimitBackend):
    """Sliding-window limiter backed by Redis sorted sets."""

    def __init__(self, redis_url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def allow(self, key: str, *, max_requests: int, window_seconds: float) -> bool:
        now = time.time()
        window_start = now - window_seconds
        pipe = self._client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, int(window_seconds) + 1)
        _, _, count, _ = pipe.execute()
        if count > max_requests:
            self._client.zrem(key, str(now))
            return False
        return True

    def reset(self) -> None:
        for key in self._client.scan_iter("rate_limit:*"):
            self._client.delete(key)


class RateLimiter:
    def __init__(self, backend: RateLimitBackend) -> None:
        self._backend = backend

    def allow(self, key: str, *, max_requests: int, window_seconds: float) -> bool:
        return self._backend.allow(
            key, max_requests=max_requests, window_seconds=window_seconds
        )

    def reset(self) -> None:
        self._backend.reset()


_limiter: RateLimiter | None = None


def _build_limiter(settings: Settings) -> RateLimiter:
    if settings.rate_limit_backend == "redis":
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL is required when RATE_LIMIT_BACKEND=redis")
        return RateLimiter(RedisRateLimitBackend(settings.redis_url))
    return RateLimiter(MemoryRateLimitBackend())


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = _build_limiter(get_settings())
    return _limiter


def reset_limiter(settings: Settings | None = None) -> RateLimiter:
    """Rebuild the process-wide limiter (tests and startup)."""
    global _limiter
    _limiter = _build_limiter(settings or get_settings())
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
        key = f"rate_limit:{scope}:{client_ip}"
        allowed = get_limiter().allow(
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
