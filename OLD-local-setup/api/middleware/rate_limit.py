"""
Redis-backed sliding-window rate limiter middleware.

Features:
  - Configurable limits per endpoint group (migration, RAG, general).
  - IP-based limiting for anonymous users; user-ID-based for authenticated.
  - Returns 429 with ``Retry-After`` header when the limit is exceeded.
  - Graceful degradation: if Redis is unreachable the request is allowed.
  - Health-check paths are exempt from rate limiting.

Algorithm: Redis sorted-set sliding window.
  - Key:  ``ratelimit:{identity}:{group}``
  - Members: UUIDs scored by their request timestamp.
  - On each request, remove entries older than the window, count remaining,
    and reject if count >= limit.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

# Endpoints exempt from rate limiting
EXEMPT_PATHS: Set[str] = {"/health", "/readiness", "/metrics", "/docs", "/redoc", "/openapi.json"}


@dataclass(frozen=True)
class RateLimitRule:
    """Defines how many requests are allowed in the given window."""

    max_requests: int
    window_seconds: int


# ── Default rules per endpoint group ──────────────────────────────

DEFAULT_RULES: Dict[str, RateLimitRule] = {
    "migration_write": RateLimitRule(max_requests=50, window_seconds=3600),
    "rag": RateLimitRule(max_requests=500, window_seconds=3600),
    "general": RateLimitRule(max_requests=5000, window_seconds=3600),
}


def _classify_request(path: str, method: str) -> str:
    """Map a request path + method to a rate-limit group name."""
    lower = path.lower()
    # Only rate-limit migration creation (POST), not reads
    if "/migration" in lower and method == "POST":
        return "migration_write"
    if "/rag" in lower:
        return "rag"
    return "general"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter backed by Redis sorted sets.

    Parameters
    ----------
    app : ASGIApp
        The ASGI application to wrap.
    redis_getter : callable
        An async callable that returns a ``redis.asyncio.Redis`` instance
        (or ``None`` when Redis is unavailable).
    rules : dict, optional
        Override the default rate-limit rules per group.
    """

    def __init__(self, app, redis_getter=None, rules: Optional[Dict[str, RateLimitRule]] = None):
        super().__init__(app)
        self._redis_getter = redis_getter
        self.rules: Dict[str, RateLimitRule] = rules or DEFAULT_RULES

    # ── Helpers ────────────────────────────────────────────────

    def _get_identity(self, request: Request) -> str:
        """
        Determine a rate-limit identity.

        Prefer the authenticated user ID stored on ``request.state`` by the
        auth dependency; fall back to client IP.
        """
        user_id = getattr(getattr(request, "state", None), "user_id", None)
        if user_id:
            return f"user:{user_id}"
        ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    async def _get_redis(self):
        """Return a Redis client or None."""
        if self._redis_getter is None:
            try:
                from api.dependencies import _redis_pool
                return _redis_pool
            except Exception:
                return None
        try:
            return await self._redis_getter()
        except Exception:
            return None

    # ── Core sliding-window check ────────────────────────────

    async def _is_rate_limited(
        self, redis_client, identity: str, group: str
    ) -> tuple[bool, int, int, int]:
        """
        Check and record a request against the sliding window.

        Returns
        -------
        (is_limited, remaining, limit, retry_after_seconds)
        """
        rule = self.rules.get(group, self.rules["general"])
        key = f"ratelimit:{identity}:{group}"
        now = time.time()
        window_start = now - rule.window_seconds

        pipe = redis_client.pipeline(transaction=True)
        # Remove expired entries
        pipe.zremrangebyscore(key, "-inf", window_start)
        # Count current entries
        pipe.zcard(key)
        # Add this request
        pipe.zadd(key, {str(uuid.uuid4()): now})
        # Set TTL so the key auto-expires after the window
        pipe.expire(key, rule.window_seconds + 60)
        results = await pipe.execute()

        current_count = results[1]  # zcard result (before add)

        if current_count >= rule.max_requests:
            # Determine when the oldest entry expires
            oldest = await redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1] + rule.window_seconds - now) + 1
            else:
                retry_after = rule.window_seconds
            retry_after = max(retry_after, 1)
            return True, 0, rule.max_requests, retry_after

        remaining = rule.max_requests - current_count - 1
        return False, max(remaining, 0), rule.max_requests, 0

    # ── Middleware dispatch ───────────────────────────────────

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        redis_client = await self._get_redis()

        # Graceful degradation: no Redis → allow through
        if redis_client is None:
            logger.debug("rate_limit.redis_unavailable", path=path)
            return await call_next(request)

        identity = self._get_identity(request)
        group = _classify_request(path, request.method)

        try:
            is_limited, remaining, limit, retry_after = await self._is_rate_limited(
                redis_client, identity, group
            )
        except Exception as exc:
            # Redis error → allow through
            logger.warning(
                "rate_limit.redis_error",
                error=str(exc),
                path=path,
            )
            return await call_next(request)

        if is_limited:
            correlation_id = getattr(
                getattr(request, "state", None), "correlation_id", None
            )
            logger.warning(
                "rate_limit.exceeded",
                identity=identity,
                group=group,
                path=path,
                retry_after=retry_after,
            )
            body = {
                "error": "RATE_LIMIT_ERROR",
                "detail": "Rate limit exceeded. Please try again later.",
                "context": {"retry_after_seconds": retry_after},
            }
            if correlation_id:
                body["correlation_id"] = correlation_id
            return JSONResponse(
                status_code=429,
                content=body,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Not limited — proceed and attach rate-limit info headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
