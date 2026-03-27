"""
Pydantic v2 schemas for request validation and response serialization.
"""

from api.schemas.common import (
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    SuccessResponse,
)
from api.schemas.migration import (
    MigrationCreate,
    MigrationList,
    MigrationResponse,
    MigrationSummary,
    MigrationUpdate,
)
from api.schemas.build import BuildCreate, BuildList, BuildResponse
from api.schemas.agent import (
    AgentPipelineStatus,
    AgentProgress,
    AgentTraceResponse,
)
from api.schemas.user import (
    Token,
    TokenPayload,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)

__all__ = [
    # Common
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    "SuccessResponse",
    # Migration
    "MigrationCreate",
    "MigrationList",
    "MigrationResponse",
    "MigrationSummary",
    "MigrationUpdate",
    # Build
    "BuildCreate",
    "BuildList",
    "BuildResponse",
    # Agent
    "AgentPipelineStatus",
    "AgentProgress",
    "AgentTraceResponse",
    # User
    "Token",
    "TokenPayload",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "UserUpdate",
]
