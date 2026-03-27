"""
Pydantic schemas for User CRUD, authentication, and JWT tokens.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Request schemas ───────────────────────────────────────────────


class UserCreate(BaseModel):
    """Request body for POST /users (registration)."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: str = Field(default="user", pattern=r"^(admin|user|viewer)$")
    tenant_id: Optional[str] = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    """Request body for PATCH /users/{id}."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = Field(default=None, pattern=r"^(admin|user|viewer)$")
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Request body for POST /auth/login."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


# ── Response schemas ──────────────────────────────────────────────


class UserResponse(BaseModel):
    """Public user representation (never exposes hashed_password)."""

    model_config = {"from_attributes": True}

    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    tenant_id: Optional[str] = None
    github_id: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ── JWT Token schemas ─────────────────────────────────────────────


class Token(BaseModel):
    """Response body for successful authentication."""

    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Token lifetime in seconds")


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str = Field(..., description="User ID (subject)")
    role: str = Field(default="user")
    tenant_id: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
