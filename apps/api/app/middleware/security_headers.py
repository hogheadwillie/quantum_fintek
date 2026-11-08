"""Browser-facing security response headers.

Complements Traefik qf-headers. Safe to stack; last write wins per header.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


DEFAULT_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to every response."""

    def __init__(
        self,
        app,
        *,
        enable_hsts: bool = False,
        hsts_max_age: int = 31536000,
        csp: str | None = DEFAULT_CSP,
    ) -> None:
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.csp = csp

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        headers.setdefault("X-XSS-Protection", "0")  # modern browsers; rely on CSP
        if self.csp:
            headers.setdefault("Content-Security-Policy", self.csp)
        # Strip accidental server fingerprint if present
        headers.pop("Server", None)
        if self.enable_hsts:
            headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={self.hsts_max_age}; includeSubDomains",
            )
        return response
