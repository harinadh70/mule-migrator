"""
SQLAlchemy ORM models for the MuleSoft-to-SpringBoot migration platform.

Import all models here so that ``Base.metadata`` discovers every table
when Alembic or ``create_all()`` runs.
"""

from api.models.base import SoftDeleteMixin, TimestampMixin
from api.models.user import User, UserRole
from api.models.migration import MigrationJob, MigrationStatus
from api.models.build import BuildJob, BuildStatus
from api.models.agent_trace import AgentTrace

__all__ = [
    # Mixins
    "SoftDeleteMixin",
    "TimestampMixin",
    # Models
    "User",
    "MigrationJob",
    "BuildJob",
    "AgentTrace",
    # Enums
    "UserRole",
    "MigrationStatus",
    "BuildStatus",
]
