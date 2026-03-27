"""
Role-based access control (RBAC) system.

Defines:
  - ``Role``:       enumeration of platform roles (admin, user, viewer).
  - ``Permission``: enumeration of fine-grained permissions.
  - ``ROLE_PERMISSIONS``: mapping from each role to its granted permissions.
  - ``require_permission()``: FastAPI dependency factory that checks
    whether the current user holds a given permission.

Usage in route handlers::

    from api.auth.permissions import Permission, require_permission

    @router.post("/migrations")
    async def create_migration(
        _: None = Depends(require_permission(Permission.CREATE_MIGRATION)),
        user: CurrentUser = Depends(get_current_active_user),
    ):
        ...
"""

from __future__ import annotations

from enum import Enum
from typing import Set

from fastapi import Depends

from api.exceptions import AuthorizationError


class Role(str, Enum):
    """Platform user roles."""

    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class Permission(str, Enum):
    """Fine-grained platform permissions."""

    # Migration operations
    CREATE_MIGRATION = "create_migration"
    VIEW_MIGRATION = "view_migration"
    DELETE_MIGRATION = "delete_migration"

    # RAG knowledge base
    MANAGE_RAG = "manage_rag"
    SEARCH_RAG = "search_rag"

    # Build/deploy
    TRIGGER_BUILD = "trigger_build"
    VIEW_BUILD = "view_build"

    # Administration
    ADMIN_PANEL = "admin_panel"
    MANAGE_USERS = "manage_users"
    MANAGE_API_KEYS = "manage_api_keys"

    # Projects
    VIEW_PROJECT = "view_project"
    EDIT_PROJECT = "edit_project"
    DELETE_PROJECT = "delete_project"


# ── Permission matrix ─────────────────────────────────────────────

ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ADMIN: set(Permission),  # full access to everything
    Role.USER: {
        Permission.CREATE_MIGRATION,
        Permission.VIEW_MIGRATION,
        Permission.DELETE_MIGRATION,
        Permission.SEARCH_RAG,
        Permission.MANAGE_RAG,
        Permission.TRIGGER_BUILD,
        Permission.VIEW_BUILD,
        Permission.VIEW_PROJECT,
        Permission.EDIT_PROJECT,
        Permission.DELETE_PROJECT,
        Permission.MANAGE_API_KEYS,
    },
    Role.VIEWER: {
        Permission.VIEW_MIGRATION,
        Permission.SEARCH_RAG,
        Permission.VIEW_BUILD,
        Permission.VIEW_PROJECT,
    },
}


def has_permission(role: str, permission: Permission) -> bool:
    """Check if a role string grants a specific permission."""
    try:
        role_enum = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(role_enum, set())


def require_permission(permission: Permission):
    """
    FastAPI dependency factory that enforces a permission check.

    The returned callable is itself a FastAPI dependency that resolves
    the current user and checks the permission.

    Usage::

        @router.delete("/migrations/{id}")
        async def delete_migration(
            _perm: None = Depends(require_permission(Permission.DELETE_MIGRATION)),
            user: CurrentUser = Depends(get_current_active_user),
        ):
            ...
    """
    from api.auth.dependencies import get_current_active_user

    async def _check(user=Depends(get_current_active_user)) -> None:
        if not has_permission(user.role, permission):
            raise AuthorizationError(
                detail=f"Permission '{permission.value}' is required. "
                f"Your role '{user.role}' does not grant it."
            )

    return _check
