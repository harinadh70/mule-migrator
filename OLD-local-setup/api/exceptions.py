"""
Custom exception hierarchy for the migration platform.

Each exception carries an HTTP status_code and detail message
so FastAPI exception handlers can translate them into proper responses.
"""

from __future__ import annotations

from typing import Any, Optional


class AppException(Exception):
    """
    Base application exception.

    All custom exceptions inherit from this so a single handler
    can catch the entire hierarchy.
    """

    status_code: int = 500
    detail: str = "An unexpected error occurred."
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        detail: Optional[str] = None,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.context = context or {}
        super().__init__(self.detail)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.error_code,
            "detail": self.detail,
        }
        if self.context:
            payload["context"] = self.context
        return payload


# ── Concrete Exceptions ──────────────────────────────────────────


class NotFoundError(AppException):
    status_code = 404
    detail = "The requested resource was not found."
    error_code = "NOT_FOUND"

    def __init__(self, resource: str = "resource", identifier: Any = None, **kwargs):
        detail = f"{resource} not found"
        if identifier is not None:
            detail = f"{resource} with id '{identifier}' not found"
        super().__init__(detail=detail, **kwargs)


class ValidationError(AppException):
    status_code = 422
    detail = "Request validation failed."
    error_code = "VALIDATION_ERROR"

    def __init__(self, detail: str = "Validation error", errors: Optional[list[dict]] = None, **kwargs):
        super().__init__(detail=detail, context={"errors": errors or []}, **kwargs)


class LLMError(AppException):
    status_code = 502
    detail = "LLM provider returned an error."
    error_code = "LLM_ERROR"

    def __init__(
        self,
        detail: str = "LLM request failed",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        ctx: dict[str, Any] = {}
        if provider:
            ctx["provider"] = provider
        if model:
            ctx["model"] = model
        super().__init__(detail=detail, context=ctx, **kwargs)


class RAGError(AppException):
    status_code = 500
    detail = "RAG pipeline encountered an error."
    error_code = "RAG_ERROR"

    def __init__(self, detail: str = "RAG pipeline error", stage: Optional[str] = None, **kwargs):
        ctx: dict[str, Any] = {}
        if stage:
            ctx["stage"] = stage
        super().__init__(detail=detail, context=ctx, **kwargs)


class AuthenticationError(AppException):
    status_code = 401
    detail = "Authentication required."
    error_code = "AUTHENTICATION_ERROR"

    def __init__(self, detail: str = "Could not validate credentials", **kwargs):
        super().__init__(detail=detail, **kwargs)


class AuthorizationError(AppException):
    status_code = 403
    detail = "Insufficient permissions."
    error_code = "AUTHORIZATION_ERROR"


class RateLimitError(AppException):
    status_code = 429
    detail = "Too many requests. Please try again later."
    error_code = "RATE_LIMIT_ERROR"

    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        ctx: dict[str, Any] = {}
        if retry_after is not None:
            ctx["retry_after_seconds"] = retry_after
        super().__init__(
            detail="Rate limit exceeded. Please try again later.",
            context=ctx,
            **kwargs,
        )


class MigrationError(AppException):
    status_code = 500
    detail = "Migration processing failed."
    error_code = "MIGRATION_ERROR"

    def __init__(self, detail: str = "Migration failed", project_id: Optional[str] = None, **kwargs):
        ctx: dict[str, Any] = {}
        if project_id:
            ctx["project_id"] = project_id
        super().__init__(detail=detail, context=ctx, **kwargs)
