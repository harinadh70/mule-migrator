"""
Authentication and authorization package for the migration platform.

Provides:
- JWT access/refresh token creation and validation (RS256)
- Password hashing with bcrypt
- FastAPI dependencies for auth enforcement
- GitHub OAuth2 integration
- Role-based permission system
- API key management with Fernet encryption
"""

from api.auth.api_keys import generate_api_key, rotate_api_key, validate_api_key
from api.auth.dependencies import (
    get_admin_user,
    get_current_active_user,
    get_current_user,
    get_optional_user,
)
from api.auth.jwt import create_access_token, create_refresh_token, decode_token
from api.auth.password import hash_password, verify_password
from api.auth.permissions import Permission, Role, require_permission

__all__ = [
    # JWT
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    # Password
    "hash_password",
    "verify_password",
    # Dependencies
    "get_current_user",
    "get_current_active_user",
    "get_admin_user",
    "get_optional_user",
    # Permissions
    "Role",
    "Permission",
    "require_permission",
    # API keys
    "generate_api_key",
    "validate_api_key",
    "rotate_api_key",
]
