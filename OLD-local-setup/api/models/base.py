"""
Enhanced base mixins for SQLAlchemy ORM models.

Provides reusable mixins for soft-delete and timestamp patterns
that can be composed with the declarative Base from api.database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, event
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """
    Adds created_at and updated_at columns with automatic timestamp management.

    created_at is set once on insert; updated_at is refreshed on every update.
    Note: The Base class in api.database already provides these columns.
    Use this mixin only when you need timestamps on a model that does NOT
    inherit from Base.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Adds a deleted_at column for soft-delete support.

    When deleted_at is non-null the row is considered "deleted" but
    remains in the database for auditing or recovery.  Queries should
    filter on ``deleted_at.is_(None)`` to exclude soft-deleted rows.
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        """Return True if the record has been soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the record as deleted with the current UTC timestamp."""
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Remove the soft-delete marker, restoring the record."""
        self.deleted_at = None
