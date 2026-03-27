"""
Pydantic schemas for agent trace data and real-time pipeline status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Response schemas ──────────────────────────────────────────────


class AgentTraceResponse(BaseModel):
    """Detailed trace for a single agent execution."""

    model_config = {"from_attributes": True}

    id: str
    migration_id: str
    agent_name: str
    status: str

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    token_usage: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    rag_queries: Optional[list[dict[str, Any]]] = None
    rag_results_used: int = 0

    error: Optional[str] = None
    fallback_used: bool = False
    output_summary: Optional[dict[str, Any]] = None


# ── Pipeline status (aggregates all agents for a migration) ──────


class AgentStatus(BaseModel):
    """Status of a single agent within the pipeline."""

    agent_name: str
    status: str = Field(..., examples=["pending", "running", "completed", "failed"])
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    token_usage: int = 0
    error: Optional[str] = None


class AgentPipelineStatus(BaseModel):
    """Aggregated real-time status of all agents for a migration."""

    migration_id: str
    overall_status: str = Field(
        ..., examples=["pending", "running", "completed", "failed"],
    )
    agents: list[AgentStatus] = Field(default_factory=list)
    total_tokens: int = 0
    total_duration_ms: Optional[int] = None


# ── WebSocket messages ───────────────────────────────────────────


class AgentProgress(BaseModel):
    """
    Schema for WebSocket progress messages pushed to clients.

    Sent as the agent pipeline executes to provide real-time updates.
    """

    migration_id: str
    agent_name: str
    status: str = Field(..., examples=["started", "progress", "completed", "failed"])
    progress_pct: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Estimated completion percentage",
    )
    message: Optional[str] = Field(
        default=None, description="Human-readable status message",
    )
    token_usage: Optional[int] = None
    timestamp: datetime
