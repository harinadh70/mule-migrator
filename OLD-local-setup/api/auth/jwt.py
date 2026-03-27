"""
JWT token creation and validation using RS256 (RSA).

Tokens carry the following claims:
  - sub:       user ID (string UUID)
  - exp:       expiration timestamp
  - iat:       issued-at timestamp
  - role:      user role (admin | user | viewer)
  - tenant_id: multi-tenant isolation key
  - type:      "access" or "refresh"

An RSA-2048 key pair is generated at startup when no keys are provided
via environment variables (``JWT_PRIVATE_KEY`` / ``JWT_PUBLIC_KEY``).

Token blacklisting (for logout) is handled via Redis: the token's ``jti``
(JWT ID) is stored in a Redis set with TTL equal to the token's remaining
lifetime.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from jose import JWTError, jwt
from pydantic import BaseModel

from api.config import get_settings
from api.exceptions import AuthenticationError

logger = structlog.get_logger(__name__)

# ── RSA key management ────────────────────────────────────────────

_private_key: Optional[str] = None
_public_key: Optional[str] = None


def _ensure_keys() -> tuple[str, str]:
    """
    Return (private_key_pem, public_key_pem).

    If the settings contain explicit PEM strings they are used directly.
    Otherwise, an RSA-2048 key pair is generated once and cached.
    """
    global _private_key, _public_key
    if _private_key and _public_key:
        return _private_key, _public_key

    settings = get_settings()

    if settings.security.jwt_private_key and settings.security.jwt_public_key:
        _private_key = settings.security.jwt_private_key
        _public_key = settings.security.jwt_public_key
        return _private_key, _public_key

    # Generate a key pair (development / first-run convenience)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    logger.warning(
        "jwt.generating_rsa_keys",
        detail="No JWT_PRIVATE_KEY / JWT_PUBLIC_KEY provided; generating ephemeral pair.",
    )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    _public_key = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return _private_key, _public_key


# ── Token payload schema ─────────────────────────────────────────


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str  # user ID
    exp: datetime
    iat: datetime
    role: str = "user"
    tenant_id: Optional[str] = None
    type: str = "access"  # "access" or "refresh"
    jti: str  # JWT ID (for blacklisting)


# ── Token creation ────────────────────────────────────────────────


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.

    Parameters
    ----------
    data : dict
        Must contain at least ``sub`` (user ID).
        May contain ``role``, ``tenant_id``.
    expires_delta : timedelta, optional
        Override the default expiry from settings.

    Returns
    -------
    str
        Encoded JWT string.
    """
    settings = get_settings()
    private_key, _ = _ensure_keys()

    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.security.access_token_expire_minutes)

    claims = {
        "sub": str(data["sub"]),
        "exp": now + expires_delta,
        "iat": now,
        "role": data.get("role", "user"),
        "tenant_id": data.get("tenant_id"),
        "type": "access",
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(claims, private_key, algorithm=settings.security.jwt_algorithm)


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT refresh token (longer-lived).

    Parameters
    ----------
    data : dict
        Must contain at least ``sub``.
    expires_delta : timedelta, optional
        Override the default 7-day expiry.

    Returns
    -------
    str
        Encoded JWT string.
    """
    settings = get_settings()
    private_key, _ = _ensure_keys()

    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(days=settings.security.refresh_token_expire_days)

    claims = {
        "sub": str(data["sub"]),
        "exp": now + expires_delta,
        "iat": now,
        "role": data.get("role", "user"),
        "tenant_id": data.get("tenant_id"),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(claims, private_key, algorithm=settings.security.jwt_algorithm)


# ── Token decoding ────────────────────────────────────────────────


async def decode_token(token: str, expected_type: str = "access") -> TokenPayload:
    """
    Decode and validate a JWT.

    Checks:
      1. Signature is valid (RS256).
      2. Token is not expired.
      3. Token type matches ``expected_type``.
      4. Token is not blacklisted in Redis.

    Raises
    ------
    AuthenticationError
        On any validation failure.
    """
    settings = get_settings()
    _, public_key = _ensure_keys()

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[settings.security.jwt_algorithm],
        )
    except JWTError as exc:
        raise AuthenticationError(detail=f"Invalid token: {exc}")

    # Validate token type
    if payload.get("type") != expected_type:
        raise AuthenticationError(
            detail=f"Expected {expected_type} token, got {payload.get('type')}"
        )

    # Check blacklist
    jti = payload.get("jti")
    if jti:
        try:
            from api.dependencies import _redis_pool

            if _redis_pool is not None:
                is_blacklisted = await _redis_pool.sismember("token:blacklist", jti)
                if is_blacklisted:
                    raise AuthenticationError(detail="Token has been revoked.")
        except AuthenticationError:
            raise
        except Exception:
            # Redis unavailable — skip blacklist check (fail open)
            logger.debug("jwt.blacklist_check_skipped", reason="redis_unavailable")

    try:
        return TokenPayload(**payload)
    except Exception as exc:
        raise AuthenticationError(detail=f"Malformed token payload: {exc}")


# ── Token blacklisting ───────────────────────────────────────────


async def blacklist_token(token: str) -> None:
    """
    Add a token's JTI to the Redis blacklist.

    The entry's TTL is set to the token's remaining lifetime so the
    blacklist is self-cleaning.
    """
    settings = get_settings()
    _, public_key = _ensure_keys()

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[settings.security.jwt_algorithm],
        )
    except JWTError:
        return  # already invalid — nothing to blacklist

    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return

    try:
        from api.dependencies import _redis_pool

        if _redis_pool is not None:
            remaining = int(exp - datetime.now(timezone.utc).timestamp())
            if remaining > 0:
                await _redis_pool.sadd("token:blacklist", jti)
                # Also set a per-JTI key with TTL for auto-cleanup
                await _redis_pool.setex(f"token:blacklisted:{jti}", remaining, "1")
    except Exception as exc:
        logger.warning("jwt.blacklist_failed", error=str(exc))
