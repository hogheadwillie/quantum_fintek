"""Structured JSON logging with OpenTelemetry-compatible trace context.

Features
--------
* JSON log lines emitted to stdout — picked up by any OTel collector sidecar.
* Every log record includes: timestamp (ISO-8601), level, logger name,
  message, service, version, environment, and (when available) trace_id,
  span_id, request_id, method, path, status_code, duration_ms, user_id.
* A ``StructuredLoggingMiddleware`` injects a per-request UUID into the ASGI
  scope and emits a single access log line per request.
* ``get_logger()`` returns a standard ``logging.Logger`` whose handler is
  pre-configured to emit JSON.  Call it in any module:

      from app.core.logging import get_logger
      log = get_logger(__name__)
      log.info("order placed", extra={"order_id": order_id, "symbol": sym})

* ``setup_logging()`` must be called once at startup (lifespan) to install the
  root JSON handler.  Calling it multiple times is safe (idempotent guard).

OpenTelemetry integration
-------------------------
When the optional ``opentelemetry-sdk`` package is installed the handler
automatically reads the active span's trace_id / span_id from the OTel context
and includes them in every log line.  If OTel is not installed the fields are
omitted gracefully — there is no hard dependency.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# ── OTel import — optional ────────────────────────────────────────────────────
try:
    from opentelemetry import trace as _otel_trace  # type: ignore[import]
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

# ── constants ─────────────────────────────────────────────────────────────────
SERVICE_NAME = "quantum-fintek-api"
SERVICE_VERSION = "0.9.0"
_REQUEST_ID_KEY = "request_id"
_SETUP_DONE = False


# ── JSON log formatter ────────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # Base fields
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
        }

        # Extra fields injected by callers via ``extra={}``
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _STDLIB_ATTRS:
                continue
            payload[key] = value

        # OTel trace context
        if _OTEL_AVAILABLE:
            try:
                span = _otel_trace.get_current_span()
                ctx = span.get_span_context()
                if ctx and ctx.is_valid:
                    payload["trace_id"] = format(ctx.trace_id, "032x")
                    payload["span_id"] = format(ctx.span_id, "016x")
            except Exception:
                pass

        # Exception info
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


# Standard LogRecord attributes to exclude from extra-field passthrough
_STDLIB_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message",
})


# ── public API ────────────────────────────────────────────────────────────────

def setup_logging(level: int = logging.INFO) -> None:
    """Install the JSON handler on the root logger (idempotent)."""
    global _SETUP_DONE
    if _SETUP_DONE:
        return

    root = logging.getLogger()
    # Remove any existing handlers (e.g. uvicorn's plain-text handler)
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _SETUP_DONE = True


def get_logger(name: str) -> logging.Logger:
    """Return a Logger guaranteed to use the JSON formatter.

    If ``setup_logging()`` has not been called yet this will call it.
    """
    if not _SETUP_DONE:
        setup_logging()
    return logging.getLogger(name)


# ── request-tracing middleware ────────────────────────────────────────────────

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Assign a ``request_id`` to every request and emit an access log line.

    The ``request_id`` (UUID4 hex) is:
    * Stored in ``request.state.request_id`` for downstream handlers to use.
    * Echoed in the ``X-Request-ID`` response header.
    * Included in the access log line alongside method, path, status, timing.
    """

    _log = logging.getLogger("quantum_fintek.access")

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        if not _SETUP_DONE:
            setup_logging()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        # Extract authenticated user sub from JWT (best-effort, no validation)
        user_id: str | None = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            import base64
            try:
                raw = auth.split(".")[1]
                raw += "=" * (4 - len(raw) % 4)
                claims = json.loads(base64.urlsafe_b64decode(raw))
                user_id = claims.get("sub")
            except Exception:
                pass

        t0 = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        response.headers["X-Request-ID"] = request_id

        self._log.info(
            "%s %s %d",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query) or None,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
                "client_ip": (
                    request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                    or (request.client.host if request.client else None)
                ),
            },
        )
        return response
