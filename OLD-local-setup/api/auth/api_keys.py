"""
API key generation, validation, rotation, and Fernet encryption at rest.

Key format: ``mst_<32-char-random>``  (prefix makes keys identifiable in
logs and config without revealing the secret portion).

Storage model:
  - The raw key is shown to the user exactly once at creation time.
  - The SHA-256 hash of the key is stored in the database for lookup.
  - The raw key is also encrypted with Fernet and stored alongside the
    hash so that admins can rotate the encryption key without
    invalidating all existing API keys.

Validation flow:
  1. Hash the incoming key.
  2. Look up the hash in the database.
  3. Verify ``is_active`` and ``expires_at``.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from api.config import get_settings
from api.exceptions import AuthenticationError

logger = structlog.get_logger(__name__)

API_KEY_PREFIX = "mst_"
API_KEY_RANDOM_LENGTH = 32  # characters of URL-safe randomness

# ── Fernet encryption ─────────────────────────────────────────────

_fernet = None


def _get_fernet():
    """
    Return a lazily-initialised Fernet instance.

    If no ``API_KEY_FERNET_KEY`` is configured, one is generated and
    logged as a warning (development convenience only).
    """
    global _fernet
    if _fernet is not None:
        return _fernet

    from cryptography.fernet import Fernet

    settings = get_settings()
    key = settings.security.api_key_fernet_key

    if not key:
        key = Fernet.generate_key().decode()
        logger.warning(
            "api_keys.generated_fernet_key",
            detail="No API_KEY_FERNET_KEY provided; generated ephemeral key. "
            "Set API_KEY_FERNET_KEY in production.",
        )

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_key(raw_key: str) -> str:
    """Encrypt a raw API key using Fernet. Returns a base64-encoded string."""
    f = _get_fernet()
    return f.encrypt(raw_key.encode()).decode()


def decrypt_key(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted API key."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


# ── Hashing ───────────────────────────────────────────────────────


def hash_api_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ── Key generation ────────────────────────────────────────────────


async def generate_api_key(
    user_id: str,
    role: str = "user",
    tenant_id: Optional[str] = None,
    label: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Generate a new API key for a user.

    Returns
    -------
    dict
        ``{ "raw_key": "mst_...", "key_id": "...", "key_hash": "...",
            "encrypted_key": "...", "label": "...", "expires_at": ... }``

    The ``raw_key`` is shown once and should be delivered to the user
    immediately.  It is NOT stored in plain text.
    """
    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(API_KEY_RANDOM_LENGTH)}"
    key_hash = hash_api_key(raw_key)
    encrypted = encrypt_key(raw_key)

    record = {
        "user_id": user_id,
        "role": role,
        "tenant_id": tenant_id,
        "key_hash": key_hash,
        "encrypted_key": encrypted,
        "label": label or "default",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }

    # Persist to database if available
    key_id = await _persist_key(record)
    record["key_id"] = key_id

    return {
        "raw_key": raw_key,
        "key_id": key_id,
        "key_hash": key_hash,
        "encrypted_key": encrypted,
        "label": record["label"],
        "expires_at": record["expires_at"],
    }


async def _persist_key(record: dict[str, Any]) -> str:
    """
    Store the API key record in the database.

    Falls back to an in-memory dict when the DB is not available.
    """
    try:
        from sqlalchemy import select
        from api.database import Base, _get_session_factory

        # Look for an ApiKey model
        api_key_model = None
        for mapper in Base.registry.mappers:
            if mapper.class_.__name__ == "ApiKey":
                api_key_model = mapper.class_
                break

        if api_key_model is not None:
            session_factory = _get_session_factory()
            async with session_factory() as session:
                db_key = api_key_model(
                    user_id=record["user_id"],
                    key_hash=record["key_hash"],
                    encrypted_key=record["encrypted_key"],
                    label=record["label"],
                    is_active=True,
                )
                if record.get("expires_at"):
                    db_key.expires_at = record["expires_at"]
                session.add(db_key)
                await session.commit()
                await session.refresh(db_key)
                return db_key.id
    except Exception as exc:
        logger.debug("api_keys.persist_fallback", error=str(exc))

    # Fallback: store in Redis or memory
    key_id = secrets.token_urlsafe(16)
    try:
        from api.dependencies import _redis_pool

        if _redis_pool is not None:
            import json

            record["key_id"] = key_id
            await _redis_pool.hset(
                "api_keys:by_hash", record["key_hash"], json.dumps(record)
            )
            return key_id
    except Exception:
        pass

    # Last resort: in-memory (only for dev/testing)
    _in_memory_keys[record["key_hash"]] = {**record, "key_id": key_id}
    return key_id


# In-memory fallback store
_in_memory_keys: dict[str, dict[str, Any]] = {}


# ── Key validation ────────────────────────────────────────────────


async def validate_api_key(raw_key: str) -> Optional[dict[str, Any]]:
    """
    Validate a raw API key and return the associated user record.

    Returns
    -------
    dict or None
        User record dict with ``user_id``, ``role``, ``tenant_id``
        if valid; ``None`` otherwise.
    """
    if not raw_key or not raw_key.startswith(API_KEY_PREFIX):
        return None

    key_hash = hash_api_key(raw_key)

    # Try database first
    try:
        from sqlalchemy import select
        from api.database import Base, _get_session_factory

        api_key_model = None
        for mapper in Base.registry.mappers:
            if mapper.class_.__name__ == "ApiKey":
                api_key_model = mapper.class_
                break

        if api_key_model is not None:
            session_factory = _get_session_factory()
            async with session_factory() as session:
                stmt = select(api_key_model).where(
                    api_key_model.key_hash == key_hash,
                    api_key_model.is_active == True,  # noqa: E712
                )
                result = await session.execute(stmt)
                db_key = result.scalar_one_or_none()

                if db_key is None:
                    return None

                # Check expiration
                if hasattr(db_key, "expires_at") and db_key.expires_at:
                    exp = db_key.expires_at
                    if isinstance(exp, str):
                        exp = datetime.fromisoformat(exp)
                    if exp < datetime.now(timezone.utc):
                        return None

                return {
                    "user_id": db_key.user_id,
                    "role": getattr(db_key, "role", "user"),
                    "tenant_id": getattr(db_key, "tenant_id", None),
                    "key_id": db_key.id,
                }
    except Exception as exc:
        logger.debug("api_keys.validate_db_fallback", error=str(exc))

    # Try Redis
    try:
        from api.dependencies import _redis_pool

        if _redis_pool is not None:
            import json

            data = await _redis_pool.hget("api_keys:by_hash", key_hash)
            if data:
                record = json.loads(data)
                if not record.get("is_active", True):
                    return None
                if record.get("expires_at"):
                    exp = datetime.fromisoformat(record["expires_at"])
                    if exp < datetime.now(timezone.utc):
                        return None
                return {
                    "user_id": record["user_id"],
                    "role": record.get("role", "user"),
                    "tenant_id": record.get("tenant_id"),
                    "key_id": record.get("key_id"),
                }
    except Exception:
        pass

    # Try in-memory fallback
    record = _in_memory_keys.get(key_hash)
    if record and record.get("is_active", True):
        if record.get("expires_at"):
            exp = datetime.fromisoformat(record["expires_at"])
            if exp < datetime.now(timezone.utc):
                return None
        return {
            "user_id": record["user_id"],
            "role": record.get("role", "user"),
            "tenant_id": record.get("tenant_id"),
            "key_id": record.get("key_id"),
        }

    return None


# ── Key rotation ──────────────────────────────────────────────────


async def rotate_api_key(
    old_raw_key: str,
    user_id: str,
    role: str = "user",
    tenant_id: Optional[str] = None,
    label: Optional[str] = None,
) -> dict[str, Any]:
    """
    Rotate an API key: validate the old key, deactivate it, and issue a new one.

    Parameters
    ----------
    old_raw_key : str
        The current (soon-to-be-revoked) API key.
    user_id : str
        The owning user's ID.
    role : str
        Role to assign to the new key.
    tenant_id : str, optional
        Tenant scope.
    label : str, optional
        Human-readable label for the new key.

    Returns
    -------
    dict
        The new key record (same shape as ``generate_api_key`` output).

    Raises
    ------
    AuthenticationError
        If the old key is invalid.
    """
    # Validate the old key
    existing = await validate_api_key(old_raw_key)
    if existing is None or existing["user_id"] != user_id:
        raise AuthenticationError(detail="Invalid API key for rotation.")

    # Deactivate old key
    old_hash = hash_api_key(old_raw_key)
    await _deactivate_key(old_hash)

    # Generate new key
    new_key = await generate_api_key(
        user_id=user_id,
        role=role,
        tenant_id=tenant_id,
        label=label,
    )

    logger.info(
        "api_key.rotated",
        user_id=user_id,
        old_key_hash=old_hash[:12] + "...",
        new_key_id=new_key["key_id"],
    )

    return new_key


async def _deactivate_key(key_hash: str) -> None:
    """Mark an API key as inactive in all storage layers."""
    # Database
    try:
        from sqlalchemy import update
        from api.database import Base, _get_session_factory

        api_key_model = None
        for mapper in Base.registry.mappers:
            if mapper.class_.__name__ == "ApiKey":
                api_key_model = mapper.class_
                break

        if api_key_model is not None:
            session_factory = _get_session_factory()
            async with session_factory() as session:
                stmt = (
                    update(api_key_model)
                    .where(api_key_model.key_hash == key_hash)
                    .values(is_active=False)
                )
                await session.execute(stmt)
                await session.commit()
                return
    except Exception:
        pass

    # Redis
    try:
        from api.dependencies import _redis_pool

        if _redis_pool is not None:
            await _redis_pool.hdel("api_keys:by_hash", key_hash)
            return
    except Exception:
        pass

    # In-memory
    if key_hash in _in_memory_keys:
        _in_memory_keys[key_hash]["is_active"] = False
