"""
Pydantic schemas for MigrationJob CRUD operations and list responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from api.schemas.common import PaginatedResponse


# ── Nested sub-schemas ────────────────────────────────────────────


class InputXmlFile(BaseModel):
    """Single XML file uploaded for migration."""

    name: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    size: int = Field(..., ge=0)


class LLMConfig(BaseModel):
    """LLM provider configuration attached to a migration request."""

    provider: str = Field(default="anthropic", max_length=50)
    model: str = Field(default="claude-sonnet-4-20250514", max_length=100)
    enabled: bool = Field(default=True)


class MigrationSummaryData(BaseModel):
    """Post-migration summary statistics."""

    flows: int = Field(default=0)
    connectors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LLMValidationData(BaseModel):
    """LLM-generated validation result for the migrated code."""

    score: float = Field(default=0.0, ge=0.0, le=100.0)
    issues: list[dict[str, Any]] = Field(default_factory=list)


class AgentTraceData(BaseModel):
    """Inline agent trace summary stored on the migration record."""

    plan: Optional[str] = None
    duration: Optional[int] = None
    tokens: Optional[int] = None


# ── Request schemas ───────────────────────────────────────────────


class MigrationCreate(BaseModel):
    """Request body for POST /migrations."""

    model_config = {"json_schema_extra": {
        "examples": [{
            "project_name": "payment-service",
            "group_id": "com.example.payments",
            "java_version": "17",
            "input_xml_files": [{"name": "mule-config.xml", "content": "<mule>...</mule>", "size": 1024}],
        }]
    }}

    project_name: str = Field(..., min_length=1, max_length=255)
    group_id: str = Field(..., min_length=1, max_length=255)
    java_version: str = Field(default="17", max_length=10)
    input_xml_files: list[InputXmlFile] = Field(..., min_length=1)
    dataweave_scripts: Optional[dict[str, str]] = Field(default=None)
    llm_config: Optional[LLMConfig] = Field(default=None)


class MigrationUpdate(BaseModel):
    """Request body for PATCH /migrations/{id}."""

    status: Optional[str] = Field(default=None, max_length=50)
    llm_config: Optional[LLMConfig] = Field(default=None)


# ── Response schemas ──────────────────────────────────────────────


class MigrationSummary(BaseModel):
    """Lightweight representation for list endpoints."""

    model_config = {"from_attributes": True}

    id: str
    status: str
    project_name: str
    group_id: str
    java_version: str
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class MigrationResponse(BaseModel):
    """Full migration record returned by detail endpoints."""

    model_config = {"from_attributes": True}

    id: str
    status: str
    project_name: str
    group_id: str
    java_version: str

    input_xml_files: Optional[list[dict[str, Any]]] = None
    dataweave_scripts: Optional[dict[str, Any]] = None
    llm_config: Optional[dict[str, Any]] = None

    output_files: Optional[dict[str, Any]] = None
    summary: Optional[dict[str, Any]] = None
    llm_validation: Optional[dict[str, Any]] = None
    agent_trace: Optional[dict[str, Any]] = None

    total_tokens_used: int = 0
    total_cost_usd: float = 0.0

    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    user_id: Optional[str] = None
    tenant_id: Optional[str] = None


MigrationList = PaginatedResponse[MigrationSummary]
