"""
MigrationJob ORM model.

Represents a single MuleSoft-to-SpringBoot migration request and tracks
its lifecycle from submission through agent processing to completion.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.base import SoftDeleteMixin


class MigrationStatus(str, enum.Enum):
    """Lifecycle states for a migration job."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MigrationJob(SoftDeleteMixin, Base):
    """
    Primary entity tracking an end-to-end migration run.

    Stores input artifacts, agent configuration, generated output,
    validation results, and cost/token accounting.
    """

    __tablename__ = "migration_jobs"

    # ── Core fields ───────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum(MigrationStatus, name="migration_status", native_enum=False),
        default=MigrationStatus.PENDING,
        nullable=False,
        index=True,
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[str] = mapped_column(String(255), nullable=False)
    java_version: Mapped[str] = mapped_column(
        String(10), default="17", nullable=False,
    )

    # ── Input artifacts (stored as JSONB) ─────────────────────
    input_xml_files: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSONB, default=list, nullable=True, comment="[{name, content, size}]",
    )
    dataweave_scripts: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True, comment="{name: content}",
    )

    # ── LLM configuration ────────────────────────────────────
    llm_config: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True,
        comment="{provider, model, enabled}",
    )

    # ── Output ───────────────────────────────────────────────
    output_files: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True,
        comment="{filepath: content}",
    )
    summary: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True,
        comment="{flows, connectors, warnings}",
    )

    # ── Validation & tracing ─────────────────────────────────
    llm_validation: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True,
        comment="{score, issues}",
    )
    agent_trace: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True,
        comment="{planner: {plan, duration, tokens}, coder: {...}, ...}",
    )

    # ── Cost accounting ──────────────────────────────────────
    total_tokens_used: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
    )
    total_cost_usd: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False,
    )

    # ── Timestamps ───────────────────────────────────────────
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )

    # ── Multi-tenancy / ownership ────────────────────────────
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True,
    )

    # ── Relationships ────────────────────────────────────────
    build_jobs: Mapped[list["BuildJob"]] = relationship(  # noqa: F821
        "BuildJob",
        back_populates="migration",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    agent_traces: Mapped[list["AgentTrace"]] = relationship(  # noqa: F821
        "AgentTrace",
        back_populates="migration",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    user: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User",
        back_populates="migrations",
        lazy="selectin",
    )

    # ── Table-level indexes ──────────────────────────────────
    __table_args__ = (
        Index("ix_migration_jobs_created_at", "created_at"),
        Index("ix_migration_jobs_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<MigrationJob id={self.id!r} project={self.project_name!r} "
            f"status={self.status!r}>"
        )

    def mark_running(self) -> None:
        """Transition the job to running state."""
        self.status = MigrationStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self) -> None:
        """Transition the job to completed state and compute duration."""
        self.status = MigrationStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def mark_failed(self) -> None:
        """Transition the job to failed state."""
        self.status = MigrationStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
