"""
Shared Pydantic schemas used across multiple domains.

Includes generic pagination, standard API envelope responses,
health-check, and error payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field, model_config

T = TypeVar("T")


# ── Generic Paginated Response ────────────────────────────────────


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope for paginated list endpoints."""

    model_config = model_config = {"from_attributes": True}

    items: list[T]
    total: int = Field(..., description="Total number of records matching the query")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, le=100, description="Records per page")
    pages: int = Field(..., ge=0, description="Total number of pages")

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


# ── Standard Responses ────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response for the /health endpoint."""

    status: str = Field(..., examples=["healthy"])
    version: str = Field(..., examples=["1.0.0"])
    environment: str = Field(..., examples=["production"])
    database: str = Field(default="unknown", examples=["connected"])
    redis: str = Field(default="unknown", examples=["connected"])
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Standard error envelope returned by exception handlers."""

    error: str = Field(..., description="Machine-readable error code")
    detail: str = Field(..., description="Human-readable error message")
    context: Optional[dict[str, Any]] = Field(
        default=None, description="Additional error context",
    )


class SuccessResponse(BaseModel):
    """Generic success envelope for operations without a domain-specific body."""

    success: bool = Field(default=True)
    message: str = Field(..., description="Human-readable success message")
    data: Optional[dict[str, Any]] = Field(
        default=None, description="Optional payload",
    )
