"""Sliding-window rate limiting middleware backed by Redis.

Configuration (via env / Settings):
  RATE_LIMIT_TRADING   – requests per window for /trading routes (default 60)
  RATE_LIMIT_WINDOW    – sliding window in seconds (default 60)
  RATE_LIMIT_GLOBAL    – requests per window for all other routes (default 600)

Each client is identified by the JWT ``sub`` claim when a Bearer token is
present, falling back to the IP address.  All state is stored in Redis with
a per-key TTL equal to the window size so keys are automatically cleaned up.
"""

from __future__ import annotations

import re
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Routes that get a tighter limit
_TRADING_RE = re.compile(r"^/trading/")

_DEFAULT_TRADING_LIMIT = 60
_DEFAULT_GLOBAL_LIMIT = 600
_DEFAULT_WINDOW = 60  # seconds


def _extract_client_id(request: Request) -> str:
    """Return JWT sub if available, else forwarded IP, else direct IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        # Fast path: decode without verifying signature — we only need the sub
        # for rate-limiting identity; auth middleware will reject invalid tokens.
        import base64, json as _json
        try:
            payload_b64 = auth.split(".")[1]
            # Pad to a multiple of 4
            padding = 4 - len(payload_b64) % 4
            payload_b64 += "=" * (padding % 4)
            payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
            if sub := payload.get("sub"):
                return f"sub:{sub}"
        except Exception:
            pass
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window (fixed-bucket approximation) rate limiter.

    Counts requests in a rolling window using a Redis INCR + EXPIRE pattern.
    The window resets sharply at each multiple of *window_seconds*, which
    gives slightly less smoothing than a true sliding window but is O(1) per
    request and needs no sorted-set cleanup.
    """

    def __init__(
        self,
        app: ASGIApp,
        trading_limit: int = _DEFAULT_TRADING_LIMIT,
        global_limit: int = _DEFAULT_GLOBAL_LIMIT,
        window_seconds: int = _DEFAULT_WINDOW,
    ) -> None:
        super().__init__(app)
        self.trading_limit = trading_limit
        self.global_limit = global_limit
        self.window_seconds = window_seconds

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Skip rate limiting for health / docs / static
        path = request.url.path
        if path in ("/health", "/", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        is_trading = bool(_TRADING_RE.match(path))
        limit = self.trading_limit if is_trading else self.global_limit

        client_id = _extract_client_id(request)
        bucket = int(time.time()) // self.window_seconds
        route_tag = "trading" if is_trading else "global"
        redis_key = f"rl:{route_tag}:{client_id}:{bucket}"

        try:
            import app.core.redis as _redis_module
            redis = await _redis_module.get_redis()
            count = await redis.incr(redis_key)
            if count == 1:
                await redis.expire(redis_key, self.window_seconds * 2)
        except Exception:
            # Redis unavailable — fail open (do not block request)
            return await call_next(request)

        if count > limit:
            retry_after = self.window_seconds - (int(time.time()) % self.window_seconds)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please slow down.",
                    "limit": limit,
                    "window_seconds": self.window_seconds,
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        response.headers["X-RateLimit-Reset"] = str(
            (bucket + 1) * self.window_seconds
        )
        return response

