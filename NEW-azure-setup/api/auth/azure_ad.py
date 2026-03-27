"""
Azure Active Directory (Entra ID) authentication.

Validates Azure AD JWT bearer tokens issued by Microsoft identity platform
and resolves/creates corresponding local user records.

Token validation follows Microsoft's recommended approach:
  1. Fetch JWKS from the Azure AD v2.0 discovery endpoint.
  2. Decode the token header to find the ``kid``.
  3. Validate signature, audience, issuer, and expiry using ``python-jose``.
  4. Return decoded claims.

JWKS keys are cached for 1 hour to avoid excessive network calls.

Requires:
  - ``python-jose[cryptography]``
  - ``httpx``
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import structlog

from api.config import get_settings
from api.exceptions import AuthenticationError

logger = structlog.get_logger(__name__)

# ── JWKS Cache ────────────────────────────────────────────────────

_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_cache_expiry: float = 0.0
_JWKS_CACHE_TTL_SECONDS: float = 3600.0  # 1 hour


def _get_jwks_uri(tenant_id: str) -> str:
    """Return the JWKS URI for the given Azure AD tenant."""
    return (
        f"https://login.microsoftonline.com/{tenant_id}"
        f"/discovery/v2.0/keys"
    )


def _get_issuer(tenant_id: str) -> str:
    """Return the expected token issuer for the given Azure AD tenant."""
    return f"https://login.microsoftonline.com/{tenant_id}/v2.0"


async def _fetch_jwks(tenant_id: str) -> Dict[str, Any]:
    """
    Fetch JWKS from Azure AD, with 1-hour in-memory cache.

    Returns
    -------
    dict
        The JWKS response containing ``keys``.

    Raises
    ------
    AuthenticationError
        If the JWKS endpoint is unreachable or returns invalid data.
    """
    global _jwks_cache, _jwks_cache_expiry

    now = time.monotonic()
    if _jwks_cache is not None and now < _jwks_cache_expiry:
        return _jwks_cache

    try:
        import httpx
    except ImportError:
        raise AuthenticationError(
            detail="httpx is required for Azure AD authentication. "
            "Install it with: pip install httpx"
        )

    jwks_uri = _get_jwks_uri(tenant_id)
    logger.info("azure_ad.fetching_jwks", uri=jwks_uri)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_uri)
            response.raise_for_status()
            jwks_data = response.json()
    except httpx.HTTPError as exc:
        logger.error("azure_ad.jwks_fetch_failed", error=str(exc))
        raise AuthenticationError(
            detail=f"Failed to fetch Azure AD JWKS: {exc}"
        )

    if "keys" not in jwks_data:
        raise AuthenticationError(
            detail="Invalid JWKS response from Azure AD (missing 'keys')."
        )

    _jwks_cache = jwks_data
    _jwks_cache_expiry = now + _JWKS_CACHE_TTL_SECONDS
    logger.info(
        "azure_ad.jwks_cached",
        key_count=len(jwks_data["keys"]),
        ttl_seconds=_JWKS_CACHE_TTL_SECONDS,
    )

    return jwks_data


def _find_signing_key(jwks: Dict[str, Any], kid: str) -> Dict[str, Any]:
    """
    Find the JWK matching the given ``kid`` (Key ID).

    Raises
    ------
    AuthenticationError
        If no matching key is found.
    """
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key

    available_kids = [k.get("kid", "?") for k in jwks.get("keys", [])]
    raise AuthenticationError(
        detail=f"No Azure AD signing key found for kid={kid}. "
        f"Available: {available_kids}"
    )


# ── Token Validation ─────────────────────────────────────────────


async def validate_azure_ad_token(token: str) -> Dict[str, Any]:
    """
    Validate an Azure AD JWT bearer token.

    Steps:
      1. Decode the token header (unverified) to extract ``kid``.
      2. Fetch JWKS from Azure AD (cached for 1 hour).
      3. Find the matching signing key.
      4. Verify the token signature, audience, issuer, and expiry.
      5. Return the decoded claims.

    Parameters
    ----------
    token : str
        The raw JWT string from the ``Authorization: Bearer`` header.

    Returns
    -------
    dict
        Decoded JWT claims (sub, name, email, oid, tid, roles, etc.).

    Raises
    ------
    AuthenticationError
        On any validation failure.
    """
    try:
        from jose import jwt as jose_jwt
        from jose import JWTError
        from jose.utils import base64url_decode
    except ImportError:
        raise AuthenticationError(
            detail="python-jose[cryptography] is required for Azure AD auth. "
            "Install it with: pip install python-jose[cryptography]"
        )

    settings = get_settings()
    tenant_id = settings.azure.azure_ad_tenant_id
    client_id = settings.azure.azure_ad_client_id

    if not tenant_id or not client_id:
        raise AuthenticationError(
            detail="Azure AD is not configured. Set AZURE_AD_TENANT_ID "
            "and AZURE_AD_CLIENT_ID."
        )

    # Step 1: Decode header (unverified) to get kid
    try:
        unverified_header = jose_jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthenticationError(
            detail=f"Invalid Azure AD token header: {exc}"
        )

    kid = unverified_header.get("kid")
    if not kid:
        raise AuthenticationError(
            detail="Azure AD token is missing 'kid' header claim."
        )

    # Step 2: Fetch JWKS
    jwks = await _fetch_jwks(tenant_id)

    # Step 3: Find signing key
    signing_key = _find_signing_key(jwks, kid)

    # Build the RSA public key from JWK components
    try:
        from jose.backends import RSAKey

        rsa_key = {
            "kty": signing_key["kty"],
            "kid": signing_key["kid"],
            "use": signing_key.get("use", "sig"),
            "n": signing_key["n"],
            "e": signing_key["e"],
        }
    except KeyError as exc:
        raise AuthenticationError(
            detail=f"Malformed Azure AD JWK: missing {exc}"
        )

    # Step 4: Verify token
    expected_issuer = _get_issuer(tenant_id)

    try:
        claims = jose_jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=expected_issuer,
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_at_hash": False,
            },
        )
    except JWTError as exc:
        logger.warning("azure_ad.token_validation_failed", error=str(exc))
        raise AuthenticationError(
            detail=f"Azure AD token validation failed: {exc}"
        )

    logger.debug(
        "azure_ad.token_validated",
        oid=claims.get("oid"),
        name=claims.get("name"),
        email=claims.get("preferred_username"),
    )

    return claims


# ── User Resolution ──────────────────────────────────────────────


async def get_azure_ad_user(
    claims: Dict[str, Any],
    db_session: Any,
) -> Any:
    """
    Resolve an Azure AD user to a local user record.

    If the user does not exist in the local database, a new record is
    created using the Azure AD claims (JIT provisioning).

    Parameters
    ----------
    claims : dict
        Decoded Azure AD JWT claims.
    db_session : AsyncSession
        SQLAlchemy async session.

    Returns
    -------
    User
        The local user model instance.
    """
    from sqlalchemy import select

    # Azure AD claims mapping
    oid = claims.get("oid", "")  # Object ID (unique per tenant)
    email = claims.get("preferred_username", claims.get("email", ""))
    name = claims.get("name", "")
    tenant_id = claims.get("tid", "")
    roles = claims.get("roles", [])

    if not oid:
        raise AuthenticationError(
            detail="Azure AD token is missing 'oid' claim."
        )

    # Try to import the User model — it may vary by project
    try:
        from api.models.user import User
    except ImportError:
        # If the User model is not available, return a dict representation
        logger.warning(
            "azure_ad.user_model_not_found",
            detail="User model not importable; returning dict.",
        )
        return {
            "id": oid,
            "email": email,
            "name": name,
            "tenant_id": tenant_id,
            "role": _map_azure_role(roles),
            "azure_oid": oid,
            "is_active": True,
        }

    # Look up by Azure OID first, then by email
    stmt = select(User).where(
        (User.azure_oid == oid) | (User.email == email)
    )
    result = await db_session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        # Update Azure OID if not set (e.g., user existed before Azure AD)
        if not getattr(user, "azure_oid", None):
            user.azure_oid = oid
        # Update name if changed
        if name and user.name != name:
            user.name = name
        await db_session.commit()
        logger.info(
            "azure_ad.user_resolved",
            user_id=str(user.id),
            email=email,
            is_new=False,
        )
        return user

    # JIT provisioning: create a new user
    new_user = User(
        email=email,
        name=name or email.split("@")[0],
        azure_oid=oid,
        tenant_id=tenant_id,
        role=_map_azure_role(roles),
        is_active=True,
        # No password hash — Azure AD users authenticate via SSO
        password_hash=None,
    )
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)

    logger.info(
        "azure_ad.user_created",
        user_id=str(new_user.id),
        email=email,
        role=new_user.role,
    )
    return new_user


def _map_azure_role(azure_roles: list) -> str:
    """
    Map Azure AD app roles to local application roles.

    Azure AD roles are configured in the app registration manifest.
    This maps them to the local role system (admin / user / viewer).
    """
    if not azure_roles:
        return "user"

    # Priority-based mapping
    role_priority = {"Admin": "admin", "Writer": "user", "Reader": "viewer"}
    for azure_role, local_role in role_priority.items():
        if azure_role in azure_roles:
            return local_role

    return "user"


def is_azure_ad_token(token: str) -> bool:
    """
    Heuristic check whether a bearer token is an Azure AD token.

    Azure AD tokens are JWTs whose issuer (``iss``) claim starts with
    ``https://login.microsoftonline.com/`` or ``https://sts.windows.net/``.
    We decode the payload without verification to check this.

    Parameters
    ----------
    token : str
        The raw JWT string.

    Returns
    -------
    bool
        True if the token appears to be from Azure AD.
    """
    try:
        from jose import jwt as jose_jwt

        # Decode without verification — we just need the iss claim
        unverified_claims = jose_jwt.get_unverified_claims(token)
        issuer = unverified_claims.get("iss", "")
        return (
            "login.microsoftonline.com" in issuer
            or "sts.windows.net" in issuer
        )
    except Exception:
        return False


def clear_jwks_cache() -> None:
    """Clear the JWKS cache (useful in tests)."""
    global _jwks_cache, _jwks_cache_expiry
    _jwks_cache = None
    _jwks_cache_expiry = 0.0
