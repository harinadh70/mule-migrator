"""
Security headers middleware.

Adds standard security headers to every HTTP response to mitigate
common web vulnerabilities (clickjacking, MIME sniffing, XSS, etc.).

CSP is configurable via settings and relaxed in development mode to
allow the Monaco editor CDN and related assets.
"""

from __future__ import annotations

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


# ── Default CSP Policies ──────────────────────────────────────────

_PRODUCTION_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)

_DEVELOPMENT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com; "
    "img-src 'self' data: blob:; "
    "font-src 'self' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com data:; "
    "connect-src 'self' ws://localhost:* http://localhost:*; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects security-related HTTP headers into every response.

    Parameters
    ----------
    app : ASGIApp
        The ASGI application.
    is_production : bool
        When ``True``, enables HSTS and uses a strict CSP.
        When ``False``, relaxes CSP for local development tooling
        (Monaco editor CDN, hot-reload WebSockets, etc.).
    csp_policy : str | None
        Override the Content-Security-Policy value entirely.
        If ``None``, uses the built-in production or development default.
    """

    def __init__(
        self,
        app,
        is_production: bool = True,
        csp_policy: Optional[str] = None,
    ) -> None:
        super().__init__(app)
        self.is_production = is_production

        if csp_policy is not None:
            self.csp_policy = csp_policy
        else:
            self.csp_policy = _PRODUCTION_CSP if is_production else _DEVELOPMENT_CSP

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # ── Always-on headers ────────────────────────────────────
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = self.csp_policy
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        # ── Production-only headers ──────────────────────────────
        if self.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        return response
