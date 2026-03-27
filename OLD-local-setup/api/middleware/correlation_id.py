"""
Correlation-ID middleware.

Assigns a unique UUID to every request so that logs, error responses,
and downstream service calls (including Celery tasks) can be correlated
back to the originating HTTP request.

The ID is:
  1. Read from the incoming ``X-Correlation-ID`` header (trusted proxies), or
  2. Generated as a new UUID-4.
  3. Stored on ``request.state.correlation_id``.
  4. Bound into the structlog context for the duration of the request.
  5. Returned in the ``X-Correlation-ID`` response header.
  6. Exposed via a :class:`contextvars.ContextVar` for Celery header propagation.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ── Context variable (usable from Celery signal hooks) ────────────

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

HEADER_NAME = "X-Correlation-ID"

logger = structlog.get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Inject and propagate a correlation ID on every request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 1. Extract or generate
        cid = request.headers.get(HEADER_NAME) or str(uuid.uuid4())

        # 2. Store on request state (available to route handlers)
        request.state.correlation_id = cid

        # 3. Set context var (available to Celery and other async code)
        token = correlation_id_ctx.set(cid)

        # 4. Bind to structlog for all log entries in this request scope
        structlog.contextvars.bind_contextvars(correlation_id=cid)

        try:
            response = await call_next(request)
        finally:
            # 5. Clean up structlog bindings
            structlog.contextvars.unbind_contextvars("correlation_id")
            correlation_id_ctx.reset(token)

        # 6. Add to response headers
        response.headers[HEADER_NAME] = cid
        return response


def get_celery_correlation_headers() -> dict[str, str]:
    """
    Return a dict suitable for ``task.apply_async(headers=...)`` so the
    correlation ID propagates into the Celery worker context.

    Usage in task dispatch::

        from api.middleware.correlation_id import get_celery_correlation_headers

        my_task.apply_async(
            args=[...],
            headers=get_celery_correlation_headers(),
        )
    """
    cid = correlation_id_ctx.get("")
    if cid:
        return {"X-Correlation-ID": cid}
    return {}
