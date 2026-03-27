"""
User ORM model.

Supports local password authentication and GitHub OAuth.
Includes role-based access control and multi-tenancy via tenant_id.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.base import SoftDeleteMixin


class UserRole(str, enum.Enum):
    """Authorization roles."""

    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(SoftDeleteMixin, Base):
    """
    Platform user with authentication credentials and RBAC role.

    Supports both local username/password auth and GitHub OAuth.
    The tenant_id column enables row-level multi-tenancy filtering.
    """

    __tablename__ = "users"

    # ── Identity ─────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True,
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )

    # ── Authorization ────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )

    # ── Multi-tenancy ────────────────────────────────────────
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True,
    )

    # ── OAuth ────────────────────────────────────────────────
    github_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True,
    )

    # ── Activity tracking ────────────────────────────────────
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Relationships ────────────────────────────────────────
    migrations: Mapped[list["MigrationJob"]] = relationship(  # noqa: F821
        "MigrationJob",
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<User id={self.id!r} username={self.username!r} "
            f"role={self.role!r}>"
        )
