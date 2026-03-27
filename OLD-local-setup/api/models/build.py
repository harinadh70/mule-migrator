"""
BuildJob ORM model.

Tracks Maven/Gradle build attempts against generated SpringBoot code
produced by a MigrationJob.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class BuildStatus(str, enum.Enum):
    """Lifecycle states for a build job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BuildJob(Base):
    """
    Records a single build execution for a migration's output project.

    Captures the build tool used, full console log, and exit code so
    failures can be diagnosed and retried.
    """

    __tablename__ = "build_jobs"

    # ── Core fields ───────────────────────────────────────────
    migration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("migration_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Enum(BuildStatus, name="build_status", native_enum=False),
        default=BuildStatus.PENDING,
        nullable=False,
    )
    build_tool: Mapped[str] = mapped_column(
        String(50), default="maven", nullable=False,
    )
    build_log: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    exit_code: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )

    # ── Timestamps ───────────────────────────────────────────
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )

    # ── Relationships ────────────────────────────────────────
    migration: Mapped["MigrationJob"] = relationship(  # noqa: F821
        "MigrationJob",
        back_populates="build_jobs",
    )

    def __repr__(self) -> str:
        return (
            f"<BuildJob id={self.id!r} migration={self.migration_id!r} "
            f"status={self.status!r}>"
        )

    def mark_running(self) -> None:
        """Transition to running state."""
        self.status = BuildStatus.RUNNING

    def mark_completed(self, exit_code: int) -> None:
        """Transition to completed/failed based on exit code."""
        self.exit_code = exit_code
        self.completed_at = datetime.now(timezone.utc)
        if self.created_at:
            delta = self.completed_at - self.created_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        self.status = BuildStatus.COMPLETED if exit_code == 0 else BuildStatus.FAILED
