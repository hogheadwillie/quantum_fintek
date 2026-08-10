"""Rate limit middleware tests.

Verifies that RateLimitMiddleware:
- Allows requests up to the configured limit
- Returns 429 with the right body + Retry-After header beyond the limit
- Injects X-RateLimit-* headers on allowed requests
- Skips rate limiting for the health endpoint

These tests use a *standalone* FastAPI app that does NOT involve app.main or
any database.  Each test injects its own FakeRedis via a conftest-style
autouse fixture so window buckets never bleed between tests.
"""

from __future__ import annotations

import os
import sys
import time

import pytest
import fakeredis.aioredis as fakeredis_async
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in [
    os.path.join(ROOT, "apps", "api"),
    os.path.join(ROOT, "packages", "quant-core", "src"),
    os.path.join(ROOT, "packages", "ai-intel", "src"),
    os.path.join(ROOT, "packages", "security", "src"),
    os.path.join(ROOT, "packages", "zos-bridge", "src"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Import the middleware module directly — no app.main dependency
import app.core.redis as _redis_core  # noqa: E402
from app.middleware.rate_limit import RateLimitMiddleware  # noqa: E402


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_app(trading_limit: int = 5, global_limit: int = 10, window: int = 60) -> FastAPI:
    """Tiny standalone test app — no DB, no lifespan."""
    _app = FastAPI()
    _app.add_middleware(
        RateLimitMiddleware,
        trading_limit=trading_limit,
        global_limit=global_limit,
        window_seconds=window,
    )

    @_app.get("/health")
    def health():
        return {"ok": True}

    @_app.get("/trading/orders")
    def trading():
        return {"orders": []}

    @_app.get("/quant/test")
    def quant():
        return {"ok": True}

    return _app


# ── autouse fixture: inject fresh redis per test ──────────────────────────────

@pytest.fixture(autouse=True)
def _inject_fresh_redis(monkeypatch):
    """Each test gets its own FakeRedis so window buckets never bleed."""
    instance = fakeredis_async.FakeRedis()

    async def _get():
        return instance

    # Patch the module attribute that RateLimitMiddleware looks up at dispatch time
    monkeypatch.setattr(_redis_core, "get_redis", _get)
    yield instance


# ── tests ──────────────────────────────────────────────────────────────────────

class TestRateLimitHeaders:
    def test_allowed_request_has_ratelimit_headers(self):
        with TestClient(_make_app(global_limit=10)) as c:
            res = c.get("/quant/test")
        assert res.status_code == 200
        assert "X-RateLimit-Limit" in res.headers
        assert "X-RateLimit-Remaining" in res.headers
        assert "X-RateLimit-Reset" in res.headers

    def test_remaining_decrements(self):
        app = _make_app(global_limit=10)
        with TestClient(app) as c:
            r1 = c.get("/quant/test")
            r2 = c.get("/quant/test")
        rem1 = int(r1.headers["X-RateLimit-Remaining"])
        rem2 = int(r2.headers["X-RateLimit-Remaining"])
        assert rem2 == rem1 - 1

    def test_limit_header_matches_config(self):
        with TestClient(_make_app(global_limit=42)) as c:
            res = c.get("/quant/test")
        assert res.headers["X-RateLimit-Limit"] == "42"

    def test_reset_header_is_future(self):
        with TestClient(_make_app(global_limit=10)) as c:
            res = c.get("/quant/test")
        reset_ts = int(res.headers["X-RateLimit-Reset"])
        assert reset_ts > int(time.time())


class TestRateLimitBlocking:
    def test_global_limit_enforced(self):
        """After limit requests, the next one gets 429."""
        limit = 3
        with TestClient(_make_app(global_limit=limit)) as c:
            for i in range(limit):
                res = c.get(f"/quant/test?i={i}")
                assert res.status_code == 200, f"Request {i} unexpectedly blocked"
            blocked = c.get("/quant/test?i=over")
        assert blocked.status_code == 429

    def test_trading_limit_enforced(self):
        """Trading endpoint uses trading_limit, not global_limit."""
        with TestClient(_make_app(trading_limit=2, global_limit=100)) as c:
            assert c.get("/trading/orders").status_code == 200
            assert c.get("/trading/orders").status_code == 200
            assert c.get("/trading/orders").status_code == 429

    def test_429_body_has_detail(self):
        with TestClient(_make_app(global_limit=1)) as c:
            c.get("/quant/test")
            res = c.get("/quant/test")
        assert res.status_code == 429
        body = res.json()
        assert "detail" in body
        assert "limit" in body
        assert "retry_after" in body

    def test_retry_after_header_present(self):
        with TestClient(_make_app(global_limit=1)) as c:
            c.get("/quant/test")
            res = c.get("/quant/test")
        assert res.status_code == 429
        assert "Retry-After" in res.headers
        assert int(res.headers["Retry-After"]) > 0

    def test_limit_value_in_429_body(self):
        limit = 2
        with TestClient(_make_app(global_limit=limit)) as c:
            c.get("/quant/test")
            c.get("/quant/test")
            res = c.get("/quant/test")
        assert res.json()["limit"] == limit

    def test_window_seconds_in_429_body(self):
        with TestClient(_make_app(global_limit=1, window=120)) as c:
            c.get("/quant/test")
            res = c.get("/quant/test")
        assert res.json()["window_seconds"] == 120


class TestRateLimitExemptions:
    def test_health_endpoint_not_rate_limited(self):
        """/health is always allowed regardless of global limit."""
        with TestClient(_make_app(global_limit=1)) as c:
            c.get("/quant/test")  # exhaust global limit
            for _ in range(5):
                assert c.get("/health").status_code == 200

    def test_trading_limit_does_not_affect_global(self):
        """Exhausting trading limit should not block non-trading routes."""
        with TestClient(_make_app(trading_limit=1, global_limit=100)) as c:
            c.get("/trading/orders")   # ok
            c.get("/trading/orders")   # blocked (429)
            assert c.get("/quant/test").status_code == 200

    def test_allowed_then_blocked_then_health(self):
        """After global exhaustion, /health is still accessible."""
        with TestClient(_make_app(global_limit=1)) as c:
            c.get("/quant/test")
            c.get("/quant/test")  # 429
            assert c.get("/health").status_code == 200
