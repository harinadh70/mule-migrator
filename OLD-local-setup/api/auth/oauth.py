"""
GitHub OAuth2 integration.

Implements the Authorization Code flow:

  1. ``get_github_auth_url()``      → build the GitHub authorize redirect URL.
  2. ``exchange_code(code)``        → exchange the authorization code for an access token.
  3. ``get_github_user(token)``     → fetch the authenticated user's profile.
  4. ``create_or_update_user(...)`` → upsert user record and return JWT tokens.
"""

from __future__ import annotations

import secrets
from typing import Any, Optional

import httpx
import structlog

from api.auth.jwt import create_access_token, create_refresh_token
from api.config import get_settings
from api.exceptions import AuthenticationError

logger = structlog.get_logger(__name__)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL = "https://api.github.com/user/emails"

# In-memory state store for CSRF protection (use Redis in production)
_oauth_states: dict[str, bool] = {}


def get_github_auth_url(state: Optional[str] = None) -> str:
    """
    Build the GitHub OAuth2 authorization redirect URL.

    Parameters
    ----------
    state : str, optional
        CSRF state parameter. Auto-generated if not supplied.

    Returns
    -------
    str
        The full authorization URL to redirect the user to.
    """
    settings = get_settings()

    if not settings.security.github_client_id:
        raise AuthenticationError(detail="GitHub OAuth is not configured.")

    if state is None:
        state = secrets.token_urlsafe(32)

    _oauth_states[state] = True

    params = {
        "client_id": settings.security.github_client_id,
        "redirect_uri": settings.security.github_redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_code(code: str, state: Optional[str] = None) -> str:
    """
    Exchange an authorization code for a GitHub access token.

    Parameters
    ----------
    code : str
        The authorization code from the callback query string.
    state : str, optional
        The CSRF state parameter to validate.

    Returns
    -------
    str
        A GitHub personal access token.

    Raises
    ------
    AuthenticationError
        If the exchange fails or state is invalid.
    """
    # Validate CSRF state if provided
    if state is not None:
        if state not in _oauth_states:
            raise AuthenticationError(detail="Invalid OAuth state parameter.")
        del _oauth_states[state]

    settings = get_settings()

    if not settings.security.github_client_id or not settings.security.github_client_secret:
        raise AuthenticationError(detail="GitHub OAuth is not configured.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.security.github_client_id,
                "client_secret": settings.security.github_client_secret,
                "code": code,
                "redirect_uri": settings.security.github_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

    if response.status_code != 200:
        logger.error(
            "oauth.github.token_exchange_failed",
            status=response.status_code,
            body=response.text,
        )
        raise AuthenticationError(detail="Failed to exchange authorization code.")

    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        error_desc = data.get("error_description", "Unknown error")
        raise AuthenticationError(detail=f"GitHub OAuth error: {error_desc}")

    return access_token


async def get_github_user(github_token: str) -> dict[str, Any]:
    """
    Fetch the authenticated user's profile from GitHub.

    Returns a dict with at least: ``id``, ``login``, ``email``, ``name``,
    ``avatar_url``.
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Fetch profile
        resp = await client.get(GITHUB_USER_URL, headers=headers)
        if resp.status_code != 200:
            raise AuthenticationError(detail="Failed to fetch GitHub user profile.")
        user_data = resp.json()

        # Email may be null on the profile; fetch from the emails endpoint
        if not user_data.get("email"):
            email_resp = await client.get(GITHUB_USER_EMAILS_URL, headers=headers)
            if email_resp.status_code == 200:
                emails = email_resp.json()
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    None,
                )
                if primary:
                    user_data["email"] = primary["email"]

    return {
        "github_id": str(user_data["id"]),
        "login": user_data.get("login", ""),
        "email": user_data.get("email"),
        "name": user_data.get("name") or user_data.get("login", ""),
        "avatar_url": user_data.get("avatar_url"),
    }


async def create_or_update_user(
    github_user: dict[str, Any],
) -> dict[str, Any]:
    """
    Create or update a local user record from GitHub profile data and
    return JWT tokens.

    This function integrates with the database layer.  If no DB session
    is available (e.g. during early development) it returns a minimal
    payload using the GitHub data directly.

    Returns
    -------
    dict
        ``{ "access_token": ..., "refresh_token": ..., "user": {...} }``
    """
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from api.database import _get_session_factory

        session_factory = _get_session_factory()
        async with session_factory() as session:
            # Try to find existing user by github_id
            from api.database import Base

            # Attempt dynamic model lookup
            user_model = None
            for mapper in Base.registry.mappers:
                if mapper.class_.__name__ == "User":
                    user_model = mapper.class_
                    break

            if user_model is not None:
                stmt = select(user_model).where(
                    user_model.github_id == github_user["github_id"]
                )
                result = await session.execute(stmt)
                db_user = result.scalar_one_or_none()

                if db_user is None:
                    # Create new user
                    db_user = user_model(
                        github_id=github_user["github_id"],
                        username=github_user["login"],
                        email=github_user.get("email"),
                        full_name=github_user.get("name"),
                        avatar_url=github_user.get("avatar_url"),
                        role="user",
                        is_active=True,
                    )
                    session.add(db_user)
                else:
                    # Update existing user
                    db_user.username = github_user["login"]
                    db_user.avatar_url = github_user.get("avatar_url")
                    if github_user.get("email"):
                        db_user.email = github_user["email"]
                    if github_user.get("name"):
                        db_user.full_name = github_user["name"]

                await session.commit()
                await session.refresh(db_user)

                user_id = db_user.id
                role = getattr(db_user, "role", "user")
                tenant_id = getattr(db_user, "tenant_id", None)
            else:
                # User model not defined yet — use GitHub ID as user ID
                user_id = github_user["github_id"]
                role = "user"
                tenant_id = None
    except Exception as exc:
        logger.warning(
            "oauth.create_or_update_user.db_fallback",
            error=str(exc),
        )
        user_id = github_user["github_id"]
        role = "user"
        tenant_id = None

    token_data = {"sub": user_id, "role": role, "tenant_id": tenant_id}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": github_user["login"],
            "email": github_user.get("email"),
            "name": github_user.get("name"),
            "avatar_url": github_user.get("avatar_url"),
            "role": role,
        },
    }
