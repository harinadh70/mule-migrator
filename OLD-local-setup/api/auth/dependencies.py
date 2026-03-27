"""
FastAPI authentication dependencies.

Provides injectable dependencies for route handlers to enforce
authentication and authorization:

  - ``get_current_user``:        extract and validate JWT from the request.
  - ``get_current_active_user``: additionally verify ``is_active``.
  - ``get_admin_user``:          additionally verify ``role == "admin"``.
  - ``get_optional_user``:       returns ``None`` when no token is present
                                 (for endpoints that work with or without auth).

Supports two authentication schemes:
  - ``Authorization: Bearer <jwt>``
  - ``X-API-Key: <api_key>``
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from api.auth.jwt import TokenPayload, decode_token
from api.config import get_settings
from api.exceptions import AuthenticationError, AuthorizationError

logger = structlog.get_logger(__name__)

# ── Security schemes ──────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ── User model (lightweight representation for request scope) ─────


class CurrentUser(BaseModel):
    """Minimal user representation carried through the request."""

    id: str
    role: str = "user"
    tenant_id: Optional[str] = None
    is_active: bool = True

    # Populated when authenticated via API key
    via_api_key: bool = False


# ── Core dependency: resolve user from JWT or API key ─────────────


async def get_current_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    api_key: Optional[str] = Depends(_api_key_header),
) -> CurrentUser:
    """
    Extract and validate credentials from the request.

    Resolution order:
      1. ``Authorization: Bearer <azure_ad_jwt>`` (if Azure AD is enabled
         and the token issuer matches login.microsoftonline.com)
      2. ``Authorization: Bearer <jwt>`` (local RS256 JWT)
      3. ``X-API-Key: <key>``

    Sets ``request.state.user_id`` for downstream use (e.g. rate limiter).

    Raises
    ------
    AuthenticationError
        If no valid credentials are found.
    """
    user: Optional[CurrentUser] = None

    # ── Try Bearer token ──────────────────────────────────
    if bearer is not None:
        user = await _resolve_bearer_token(bearer.credentials)

    # ── Fall back to API key ──────────────────────────────
    if user is None and api_key is not None:
        user = await _resolve_api_key(api_key)

    if user is None:
        raise AuthenticationError(detail="Missing or invalid credentials.")

    # Store user ID on request state for rate limiting and logging
    request.state.user_id = user.id
    return user


async def _resolve_bearer_token(token: str) -> Optional[CurrentUser]:
    """
    Resolve a bearer token to a ``CurrentUser``.

    Checks if Azure AD authentication is enabled and whether the token
    appears to be an Azure AD token. If so, validates via Azure AD.
    Otherwise, falls through to the local JWT validation.
    """
    settings = get_settings()

    # ── Azure AD path ─────────────────────────────────────
    if settings.enable_azure_ad:
        try:
            from api.auth.azure_ad import is_azure_ad_token, validate_azure_ad_token

            if is_azure_ad_token(token):
                claims = await validate_azure_ad_token(token)
                return CurrentUser(
                    id=claims.get("oid", claims.get("sub", "")),
                    role=_map_azure_ad_role(claims.get("roles", [])),
                    tenant_id=claims.get("tid"),
                    is_active=True,
                )
        except AuthenticationError:
            raise
        except Exception as exc:
            logger.warning("azure_ad.auth_failed", error=str(exc))
            # Do not fall through — if the token looks like Azure AD but
            # fails validation, that is an auth error, not a reason to
            # try local JWT.
            raise AuthenticationError(
                detail=f"Azure AD authentication failed: {exc}"
            )

    # ── Local JWT path ────────────────────────────────────
    try:
        token_payload: TokenPayload = await decode_token(token)
        return CurrentUser(
            id=token_payload.sub,
            role=token_payload.role,
            tenant_id=token_payload.tenant_id,
        )
    except AuthenticationError:
        raise
    except Exception as exc:
        logger.debug("jwt.decode_failed", error=str(exc))
        return None


def _map_azure_ad_role(roles: list) -> str:
    """Map Azure AD app roles to local role strings."""
    if not roles:
        return "user"
    role_map = {"Admin": "admin", "Writer": "user", "Reader": "viewer"}
    for azure_role, local_role in role_map.items():
        if azure_role in roles:
            return local_role
    return "user"


async def _resolve_api_key(raw_key: str) -> Optional[CurrentUser]:
    """
    Validate an API key and return the associated user.

    Returns ``None`` if the key is invalid (caller should raise).
    """
    try:
        from api.auth.api_keys import validate_api_key

        key_record = await validate_api_key(raw_key)
        if key_record is None:
            return None
        return CurrentUser(
            id=key_record["user_id"],
            role=key_record.get("role", "user"),
            tenant_id=key_record.get("tenant_id"),
            via_api_key=True,
        )
    except Exception as exc:
        logger.debug("api_key.validation_failed", error=str(exc))
        return None


# ── Convenience wrappers ──────────────────────────────────────────


async def get_current_active_user(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Ensure the authenticated user account is active."""
    if not user.is_active:
        raise AuthenticationError(detail="User account is disabled.")
    return user


async def get_admin_user(
    user: CurrentUser = Depends(get_current_active_user),
) -> CurrentUser:
    """Ensure the authenticated user has the ``admin`` role."""
    if user.role != "admin":
        raise AuthorizationError(detail="Admin privileges required.")
    return user


async def get_optional_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    api_key: Optional[str] = Depends(_api_key_header),
) -> Optional[CurrentUser]:
    """
    Return the current user if credentials are present, or ``None``.

    Useful for endpoints that behave differently for authenticated vs.
    anonymous users (e.g. showing public vs. private content).
    """
    if bearer is None and api_key is None:
        return None

    try:
        return await get_current_user(request, bearer, api_key)
    except AuthenticationError:
        return None
