"""
Structured request-logging middleware.

Logs every HTTP request with:
  - method, path, query string, status code
  - duration in milliseconds
  - correlation ID (from request state)
  - request body size for mutating methods (POST/PUT/PATCH)
  - client IP address

Health-check endpoints (``/health``, ``/readiness``, ``/metrics``) are
skipped to reduce noise.  Requests taking longer than
``SLOW_REQUEST_THRESHOLD_SECONDS`` (default 5 s) are logged at WARNING.
"""

from __future__ import annotations

import time
from typing import Set

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

# Endpoints to skip in the request log
SKIP_PATHS: Set[str] = {"/health", "/readiness", "/metrics"}

# Requests slower than this threshold trigger a WARNING
SLOW_REQUEST_THRESHOLD_SECONDS: float = 5.0


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request/response pair with structured metadata."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip noisy health-check endpoints
        if path in SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()

        # Gather request metadata
        method = request.method
        query = str(request.url.query) if request.url.query else None
        client_ip = request.client.host if request.client else "unknown"
        correlation_id = getattr(request.state, "correlation_id", None)

        # Body size for mutating methods (read from content-length header
        # so we never consume the request body stream).
        body_size: int | None = None
        if method in {"POST", "PUT", "PATCH"}:
            cl = request.headers.get("content-length")
            body_size = int(cl) if cl else None

        # Execute the downstream handler
        response = await call_next(request)

        duration_s = time.perf_counter() - start
        duration_ms = round(duration_s * 1000, 2)
        status = response.status_code

        log_kwargs: dict = {
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        }
        if correlation_id:
            log_kwargs["correlation_id"] = correlation_id
        if query:
            log_kwargs["query"] = query
        if body_size is not None:
            log_kwargs["request_body_bytes"] = body_size

        # Choose log level
        if duration_s >= SLOW_REQUEST_THRESHOLD_SECONDS:
            logger.warning("http.request.slow", **log_kwargs)
        elif status >= 500:
            logger.error("http.request", **log_kwargs)
        elif status >= 400:
            logger.warning("http.request", **log_kwargs)
        else:
            logger.info("http.request", **log_kwargs)

        return response
