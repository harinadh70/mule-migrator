"""
Pydantic schemas for BuildJob CRUD operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from api.schemas.common import PaginatedResponse


# ── Request schemas ───────────────────────────────────────────────


class BuildCreate(BaseModel):
    """Request body for POST /migrations/{id}/builds."""

    build_tool: str = Field(default="maven", max_length=50)


# ── Response schemas ──────────────────────────────────────────────


class BuildResponse(BaseModel):
    """Full build record."""

    model_config = {"from_attributes": True}

    id: str
    migration_id: str
    status: str
    build_tool: str
    build_log: Optional[str] = None
    exit_code: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


BuildList = PaginatedResponse[BuildResponse]
