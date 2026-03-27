"""
Tests for the health and readiness probe endpoints.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client):
    """GET /health should return 200 with status=ok and a version string."""
    response = await client.get("/health")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert isinstance(body["version"], str)


@pytest.mark.asyncio
async def test_readiness_endpoint(client):
    """
    GET /readiness should return a JSON body with ``status`` and ``checks``.

    In the test environment external services are not running, so the
    endpoint may return 503 (degraded) — but the response shape must be
    correct regardless.
    """
    response = await client.get("/readiness")

    # Accept either 200 (all healthy) or 503 (degraded)
    assert response.status_code in (200, 503)

    body = response.json()
    assert "status" in body
    assert body["status"] in ("ok", "degraded")
    assert "version" in body
    assert "checks" in body
    assert isinstance(body["checks"], dict)
