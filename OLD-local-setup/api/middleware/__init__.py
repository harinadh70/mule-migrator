"""
Middleware stack for the MuleSoft-to-SpringBoot Migration API.

Provides:
- Correlation ID injection and propagation
- Structured request/response logging
- Redis-backed sliding-window rate limiting
- Global exception handling with consistent JSON error responses
"""

from api.middleware.correlation_id import CorrelationIdMiddleware
from api.middleware.error_handler import ErrorHandlerMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.request_logging import RequestLoggingMiddleware
# SecurityHeadersMiddleware available in azure-deployment/
# from api.middleware.security_headers import SecurityHeadersMiddleware

__all__ = [
    "CorrelationIdMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitMiddleware",
    "ErrorHandlerMiddleware",
]
