"""
Password hashing and verification using bcrypt via passlib.

Uses the ``bcrypt`` scheme with automatic salt generation and the
default 12-round cost factor.  The ``deprecated="auto"`` setting
allows passlib to transparently re-hash passwords that use older
(weaker) schemes on successful verification.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(plain: str) -> str:
    """
    Hash a plain-text password and return the bcrypt digest.

    Parameters
    ----------
    plain : str
        The plain-text password.

    Returns
    -------
    str
        A bcrypt hash string (e.g. ``$2b$12$...``).
    """
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Parameters
    ----------
    plain : str
        The plain-text password to check.
    hashed : str
        The stored bcrypt hash.

    Returns
    -------
    bool
        ``True`` if the password matches.
    """
    return _pwd_context.verify(plain, hashed)
