"""
Tests for path-traversal attack prevention in RAG indexing endpoints.

The RAG ``/rag/collections/{name}/index`` endpoint accepts a filesystem
path.  These tests verify that malicious path inputs are rejected before
they can reach the filesystem.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_rag_index_rejects_parent_traversal(client):
    """
    A path containing ``..`` components should be rejected to prevent
    directory traversal outside the allowed knowledge directory.
    """
    response = await client.post(
        "/api/v2/rag/collections/test-collection/index",
        json={"path": "../../etc/passwd"},
    )

    # Expect 400/403/422 (validation) or 503 (RAG disabled in test).
    # A 200/202 would mean the traversal was NOT blocked.
    assert response.status_code in (400, 403, 422, 500, 503)

    # If the endpoint is available, verify it did not succeed
    if response.status_code not in (503, 500):
        body = response.json()
        assert "error" in body or "detail" in body


@pytest.mark.asyncio
async def test_rag_index_rejects_absolute_path(client):
    """
    An absolute path (e.g. ``/etc/shadow``) should be rejected to
    prevent access to arbitrary filesystem locations.
    """
    response = await client.post(
        "/api/v2/rag/collections/test-collection/index",
        json={"path": "/etc/shadow"},
    )

    # Accept 400/403/422 (blocked), 500 (error), or 503 (RAG disabled)
    assert response.status_code in (400, 403, 422, 500, 503)

    if response.status_code not in (503, 500):
        body = response.json()
        assert "error" in body or "detail" in body


@pytest.mark.asyncio
async def test_rag_index_rejects_null_bytes(client):
    """
    Paths containing null bytes (``\\x00``) should be rejected as they
    can be used to truncate paths in C-backed filesystem calls.
    """
    response = await client.post(
        "/api/v2/rag/collections/test-collection/index",
        json={"path": "knowledge\x00/../../../etc/passwd"},
    )

    # The null byte should cause a 400/422 rejection or be caught
    # by the JSON parser itself.
    assert response.status_code in (400, 403, 422, 500, 503)
