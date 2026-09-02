"""Rate-limiting tests for sensitive auth endpoints (ADR-003)."""
import pytest


@pytest.mark.integration
async def test_login_is_rate_limited(rate_limited_client):
    payload = {"email": "nobody@example.com", "password": "whatever-123"}

    codes = []
    for _ in range(5):
        resp = await rate_limited_client.post("/api/v1/auth/login", json=payload)
        codes.append(resp.status_code)

    # Configured max is 3/window: first three are processed (401 invalid creds),
    # subsequent attempts are rejected with 429.
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


@pytest.mark.unit
def test_limiter_sliding_window():
    from app.core.rate_limit import RateLimiter

    limiter = RateLimiter()
    assert limiter.allow("k", max_requests=2, window_seconds=60)
    assert limiter.allow("k", max_requests=2, window_seconds=60)
    assert not limiter.allow("k", max_requests=2, window_seconds=60)
    # A different key is independent.
    assert limiter.allow("other", max_requests=2, window_seconds=60)
