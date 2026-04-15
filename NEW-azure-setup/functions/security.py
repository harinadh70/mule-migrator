"""
Security module for Azure Functions.

Provides:
  - Azure AD token validation (via App Service EasyAuth headers)
  - Role-based access control (RBAC)
  - Input validation (XXE prevention for XML payloads)
  - Rate limiting via Redis
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

import defusedxml.ElementTree as SafeET
import redis as sync_redis

logger = logging.getLogger("security")


# ---------------------------------------------------------------------------
#  Azure AD authentication (App Service EasyAuth)
# ---------------------------------------------------------------------------

class AuthUser:
    """Represents an authenticated user extracted from Azure AD headers."""

    __slots__ = ("oid", "email", "name", "roles", "raw_claims")

    def __init__(
        self,
        oid: str,
        email: str,
        name: str = "",
        roles: Optional[list[str]] = None,
        raw_claims: Optional[dict[str, Any]] = None,
    ):
        self.oid = oid
        self.email = email
        self.name = name
        self.roles = roles or ["user"]
        self.raw_claims = raw_claims or {}

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def to_dict(self) -> dict[str, Any]:
        return {
            "oid": self.oid,
            "email": self.email,
            "name": self.name,
            "roles": self.roles,
        }


def validate_azure_ad_principal(
    headers: dict[str, str],
) -> Optional[AuthUser]:
    """
    Extract and validate the Azure AD user from App Service authentication
    headers.

    Azure App Service injects ``x-ms-client-principal`` (base64-encoded JSON)
    after authenticating the user.  This function decodes it and returns an
    AuthUser object.

    Args:
        headers: HTTP request headers (case-insensitive dict).

    Returns:
        AuthUser if valid principal found, else None.
    """
    principal_header = headers.get("x-ms-client-principal", "")
    if not principal_header:
        # In development, allow unauthenticated access
        if os.getenv("ENVIRONMENT", "production") == "development":
            return AuthUser(
                oid="dev-user",
                email="dev@localhost",
                name="Development User",
                roles=["admin"],
            )
        return None

    try:
        decoded = base64.b64decode(principal_header)
        principal = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("auth.invalid_principal_header: %s", exc)
        return None

    claims = {}
    for claim in principal.get("claims", []):
        typ = claim.get("typ", "")
        val = claim.get("val", "")
        claims[typ] = val

    oid = (
        claims.get("http://schemas.microsoft.com/identity/claims/objectidentifier")
        or claims.get("oid")
        or principal.get("userId", "")
    )
    email = (
        claims.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress")
        or claims.get("preferred_username")
        or claims.get("email")
        or ""
    )
    name = (
        claims.get("name")
        or claims.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")
        or ""
    )
    roles = principal.get("roles", [])
    if not roles:
        role_claim = claims.get("http://schemas.microsoft.com/ws/2008/06/identity/claims/role", "")
        if role_claim:
            roles = [r.strip() for r in role_claim.split(",")]
        else:
            roles = ["user"]

    if not oid:
        logger.warning("auth.no_oid_in_principal")
        return None

    return AuthUser(
        oid=oid,
        email=email,
        name=name,
        roles=roles,
        raw_claims=claims,
    )


def _validate_bearer_token(headers: dict[str, str]) -> Optional[AuthUser]:
    """
    Validate a Bearer token from the Authorization header.

    Supports:
      1. Azure AD JWTs (3-part tokens from MSAL acquireTokenSilent)
      2. Custom 2-part HMAC tokens (email/password login)
      3. Legacy "msal" literal (backwards-compat)
    """
    import hmac as _hmac

    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    # Legacy "Bearer msal" fallback (old frontend)
    if auth_header == "Bearer msal":
        admin_email = os.environ.get("ADMIN_EMAIL", "").lower()
        return AuthUser(
            oid="msal-user",
            email=admin_email or "msal@user",
            name=admin_email.split("@")[0] if admin_email else "MSAL User",
            roles=["admin"],
        )

    token = auth_header[7:]
    jwt_parts = token.split(".")

    # ── Azure AD JWT (3-part: header.payload.signature) ──────────
    if len(jwt_parts) == 3:
        try:
            payload_b64 = jwt_parts[1]
            padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))

            # Verify not expired
            if payload.get("exp", 0) < time.time():
                logger.warning("azure_ad_jwt.expired")
                return None

            # Verify audience matches our app registration
            aud = payload.get("aud", "")
            expected_client_id = os.environ.get(
                "AZURE_AD_CLIENT_ID", "562164fe-698a-4b4a-b874-40025140f008"
            )
            if aud != expected_client_id and aud != f"api://{expected_client_id}":
                logger.warning(
                    "azure_ad_jwt.audience_mismatch: got=%s expected=%s",
                    aud, expected_client_id,
                )
                return None

            email = (
                payload.get("preferred_username")
                or payload.get("email")
                or payload.get("upn", "")
            )
            name = payload.get("name", "")
            oid = payload.get("oid", "")
            roles = payload.get("roles", [])
            if not roles:
                # Default to admin for now (single-tenant app)
                admin_email = os.environ.get("ADMIN_EMAIL", "").lower()
                roles = ["admin"] if email.lower() == admin_email else ["user"]

            return AuthUser(
                oid=oid or email,
                email=email,
                name=name,
                roles=roles,
            )
        except Exception as exc:
            logger.warning("azure_ad_jwt.decode_error: %s", exc)
            return None

    # ── Custom 2-part HMAC token (email/password login) ──────────
    if len(jwt_parts) == 2:
        try:
            payload_b64, sig = jwt_parts

            secret = os.environ.get("JWT_SECRET", os.environ.get("AzureWebJobsStorage", "default-secret"))
            expected_sig = _hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
            if not _hmac.compare_digest(sig, expected_sig):
                return None

            padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))

            if payload.get("exp", 0) < time.time():
                return None

            email = payload.get("email", "")
            admin_email = os.environ.get("ADMIN_EMAIL", "").lower()
            roles = ["admin"] if email == admin_email else ["user"]

            return AuthUser(
                oid=email,
                email=email,
                name=payload.get("name", ""),
                roles=roles,
            )
        except Exception as exc:
            logger.warning("bearer_token.validation_error: %s", exc)
            return None

    return None


def require_auth(headers: dict[str, str]) -> AuthUser:
    """
    Validate authentication and return the user.

    Checks in order:
      1. Custom Bearer token (email/password login)
      2. Azure AD EasyAuth principal header

    Raises ValueError if not authenticated.
    """
    # Try custom Bearer token first
    user = _validate_bearer_token(headers)
    if user is not None:
        return user

    # Try Azure AD EasyAuth
    user = validate_azure_ad_principal(headers)
    if user is not None:
        return user

    raise ValueError("Authentication required. No valid Azure AD principal found.")


def require_role(headers: dict[str, str], role: str) -> AuthUser:
    """
    Validate authentication and require a specific role.

    Raises ValueError if not authenticated or missing the required role.
    """
    user = require_auth(headers)
    if not user.has_role(role) and not user.has_role("admin"):
        raise ValueError(f"Insufficient permissions. Required role: {role}")
    return user


# ---------------------------------------------------------------------------
#  XML input validation (XXE prevention)
# ---------------------------------------------------------------------------

def validate_xml_input(xml_content: str) -> str:
    """
    Validate XML content for safety.

    Uses defusedxml to reject:
      - External entity declarations (XXE)
      - Billion-laughs / exponential entity expansion
      - External DTD references
      - Processing instructions that could be harmful

    Returns the content unchanged if safe.

    Raises:
        ValueError: If the XML contains unsafe constructs or is malformed.
    """
    if not xml_content or not xml_content.strip():
        raise ValueError("XML content is empty.")

    # Size limit: 10 MB
    if len(xml_content) > 10 * 1024 * 1024:
        raise ValueError("XML content exceeds 10 MB size limit.")

    try:
        SafeET.fromstring(xml_content.encode("utf-8"))
    except SafeET.ParseError as exc:
        raise ValueError(f"Malformed or unsafe XML: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"XML validation error: {exc}") from exc

    return xml_content


def validate_xml_files(xml_files: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Validate all XML file entries in a migration request.

    Each entry should be a dict with ``name`` and ``content`` keys.

    Raises ValueError on the first invalid file.
    """
    if not xml_files:
        raise ValueError("At least one XML file is required.")

    validated = []
    for i, entry in enumerate(xml_files):
        name = entry.get("name", f"file_{i}.xml")
        content = entry.get("content", "")
        if not content.strip():
            raise ValueError(f"XML file '{name}' is empty.")
        validate_xml_input(content)
        validated.append({"name": name, "content": content})

    return validated


# ---------------------------------------------------------------------------
#  Rate limiting via Redis
# ---------------------------------------------------------------------------

_redis_client: Optional[sync_redis.Redis] = None


def _get_redis() -> Optional[sync_redis.Redis]:
    """Get the Redis client for rate limiting (sync, since Azure Functions triggers are sync context)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        return None

    try:
        _redis_client = sync_redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning("redis.rate_limit_init_failed: %s", exc)
        _redis_client = None
        return None


def check_rate_limit(
    identifier: str,
    max_requests: int = 60,
    window_seconds: int = 60,
) -> tuple[bool, dict[str, Any]]:
    """
    Check and enforce a sliding-window rate limit.

    Args:
        identifier:     Unique key (e.g. user OID or IP).
        max_requests:   Maximum requests allowed in the window.
        window_seconds: Window duration in seconds.

    Returns:
        Tuple of (allowed: bool, info: dict).
        ``info`` contains ``limit``, ``remaining``, ``reset_at``.
    """
    r = _get_redis()
    if r is None:
        # Redis unavailable — fail open
        return True, {
            "limit": max_requests,
            "remaining": max_requests,
            "reset_at": int(time.time()) + window_seconds,
        }

    key = f"ratelimit:{identifier}"
    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {f"{now}:{hashlib.md5(str(now).encode()).hexdigest()[:8]}": now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds + 1)
    results = pipe.execute()

    current_count = results[2]
    allowed = current_count <= max_requests
    remaining = max(0, max_requests - current_count)

    info = {
        "limit": max_requests,
        "remaining": remaining,
        "reset_at": int(now) + window_seconds,
    }

    if not allowed:
        logger.warning(
            "rate_limit.exceeded: identifier=%s count=%d limit=%d",
            identifier, current_count, max_requests,
        )

    return allowed, info
