"""
AgentTrace ORM model.

Captures per-agent execution details within a migration pipeline,
including token usage, RAG retrieval stats, timing, and error info.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class AgentTrace(Base):
    """
    Detailed telemetry for a single agent's execution within a migration.

    Each migration pipeline may invoke multiple agents (planner, coder,
    reviewer, etc.).  This table stores one row per agent invocation so
    the platform can surface per-agent cost, latency, and quality metrics.
    """

    __tablename__ = "agent_traces"

    # ── Foreign key ──────────────────────────────────────────
    migration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("migration_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Agent identification ─────────────────────────────────
    agent_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending",
    )

    # ── Timing ───────────────────────────────────────────────
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )

    # ── Token accounting ─────────────────────────────────────
    token_usage: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )

    # ── RAG metrics ──────────────────────────────────────────
    rag_queries: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSONB, default=list, nullable=True,
    )
    rag_results_used: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )

    # ── Error handling ───────────────────────────────────────
    error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    fallback_used: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )

    # ── Output ───────────────────────────────────────────────
    output_summary: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True,
    )

    # ── Relationships ────────────────────────────────────────
    migration: Mapped["MigrationJob"] = relationship(  # noqa: F821
        "MigrationJob",
        back_populates="agent_traces",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentTrace id={self.id!r} agent={self.agent_name!r} "
            f"status={self.status!r}>"
        )

    def mark_started(self) -> None:
        """Record agent start time."""
        self.status = "running"
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self) -> None:
        """Record agent completion and compute duration."""
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        self.token_usage = self.prompt_tokens + self.completion_tokens

    def mark_failed(self, error_message: str) -> None:
        """Record agent failure."""
        self.status = "failed"
        self.error = error_message
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
