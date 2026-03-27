"""
Tests for the SecurityHeadersMiddleware.

Verifies that every response includes the expected security headers.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_x_content_type_options_header(client):
    """Every response must include X-Content-Type-Options: nosniff."""
    response = await client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.asyncio
async def test_x_frame_options_header(client):
    """Every response must include X-Frame-Options: DENY."""
    response = await client.get("/health")
    assert response.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_referrer_policy_header(client):
    """Every response must include Referrer-Policy: strict-origin-when-cross-origin."""
    response = await client.get("/health")
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_csp_header_present(client):
    """Every response must include a Content-Security-Policy header."""
    response = await client.get("/health")
    csp = response.headers.get("content-security-policy")
    assert csp is not None
    assert "default-src" in csp


@pytest.mark.asyncio
async def test_permissions_policy_header(client):
    """Every response must include a Permissions-Policy header."""
    response = await client.get("/health")
    pp = response.headers.get("permissions-policy")
    assert pp is not None
    assert "camera=()" in pp
    assert "microphone=()" in pp
    assert "geolocation=()" in pp


@pytest.mark.asyncio
async def test_hsts_absent_in_non_production(client):
    """
    Strict-Transport-Security should NOT be set when the environment
    is not production (test settings use ``testing``).
    """
    response = await client.get("/health")
    # In testing mode, HSTS should be absent
    assert response.headers.get("strict-transport-security") is None
