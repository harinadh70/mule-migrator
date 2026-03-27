"""
Global exception-handling middleware.

Catches all exceptions that escape route handlers and converts them into
consistent JSON error responses.  The mapping is:

  - :class:`AppException` hierarchy → status code and payload from the exception.
  - :class:`pydantic.ValidationError` → 422 Unprocessable Entity.
  - :class:`sqlalchemy.exc.SQLAlchemyError` → 500 Internal Server Error.
  - Any other :class:`Exception` → 500 with a safe, generic message.

All error responses include the ``correlation_id`` when available, and all
5xx errors are logged with a full traceback.
"""

from __future__ import annotations

import traceback
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.exceptions import AppException, RateLimitError

logger = structlog.get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catch all unhandled exceptions and return structured JSON errors."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = getattr(
            getattr(request, "state", None), "correlation_id", None
        )
        try:
            return await call_next(request)
        except Exception as exc:
            return self._handle_exception(exc, request, correlation_id)

    # ── Internal helpers ──────────────────────────────────────

    def _build_response(
        self,
        status_code: int,
        error_code: str,
        detail: str,
        correlation_id: str | None,
        headers: dict[str, str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> JSONResponse:
        body: dict[str, Any] = {
            "error": error_code,
            "detail": detail,
        }
        if correlation_id:
            body["correlation_id"] = correlation_id
        if context:
            body["context"] = context
        return JSONResponse(
            status_code=status_code,
            content=body,
            headers=headers or {},
        )

    def _handle_exception(
        self,
        exc: Exception,
        request: Request,
        correlation_id: str | None,
    ) -> JSONResponse:
        # ── AppException hierarchy ──────────────────────────
        if isinstance(exc, AppException):
            headers: dict[str, str] = {}
            if isinstance(exc, RateLimitError) and exc.context.get("retry_after_seconds"):
                headers["Retry-After"] = str(exc.context["retry_after_seconds"])

            if exc.status_code >= 500:
                logger.error(
                    "app_exception.server_error",
                    error_code=exc.error_code,
                    detail=exc.detail,
                    path=request.url.path,
                    traceback=traceback.format_exc(),
                    correlation_id=correlation_id,
                )
            else:
                logger.warning(
                    "app_exception",
                    error_code=exc.error_code,
                    detail=exc.detail,
                    path=request.url.path,
                    correlation_id=correlation_id,
                )

            return self._build_response(
                status_code=exc.status_code,
                error_code=exc.error_code,
                detail=exc.detail,
                correlation_id=correlation_id,
                headers=headers,
                context=exc.context if exc.context else None,
            )

        # ── Pydantic ValidationError ───────────────────────
        try:
            from pydantic import ValidationError as PydanticValidationError

            if isinstance(exc, PydanticValidationError):
                logger.warning(
                    "validation_error",
                    path=request.url.path,
                    errors=str(exc.errors()),
                    correlation_id=correlation_id,
                )
                return self._build_response(
                    status_code=422,
                    error_code="VALIDATION_ERROR",
                    detail="Request validation failed.",
                    correlation_id=correlation_id,
                    context={"errors": exc.errors()},
                )
        except ImportError:
            pass

        # ── SQLAlchemy errors ──────────────────────────────
        try:
            from sqlalchemy.exc import SQLAlchemyError

            if isinstance(exc, SQLAlchemyError):
                logger.error(
                    "database_error",
                    path=request.url.path,
                    error=str(exc),
                    traceback=traceback.format_exc(),
                    correlation_id=correlation_id,
                )
                return self._build_response(
                    status_code=500,
                    error_code="DATABASE_ERROR",
                    detail="A database error occurred.",
                    correlation_id=correlation_id,
                )
        except ImportError:
            pass

        # ── Generic / unknown exception ────────────────────
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            exception_type=type(exc).__qualname__,
            error=str(exc),
            traceback=traceback.format_exc(),
            correlation_id=correlation_id,
        )
        return self._build_response(
            status_code=500,
            error_code="INTERNAL_ERROR",
            detail="An unexpected internal error occurred.",
            correlation_id=correlation_id,
        )
