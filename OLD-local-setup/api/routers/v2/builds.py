"""
V2 Build endpoints — Maven/Gradle build job management.

Routes:
  POST  /migrations/{migration_id}/builds  → Trigger a build
  GET   /builds/{id}                        → Build status + log
  GET   /migrations/{migration_id}/builds   → List builds for migration
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.services.build_service import BuildService

router = APIRouter()


# ── Request / Response Schemas ────────────────────────────────────────


class BuildCreateRequest(BaseModel):
    """Payload for triggering a new build."""

    build_tool: str = Field(
        default="maven",
        description="Build tool to use (maven or gradle).",
    )


class BuildResponse(BaseModel):
    """Build job details."""

    id: str
    migration_id: str
    status: str
    build_tool: str
    exit_code: Optional[int] = None
    build_log: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None

    class Config:
        from_attributes = True


# ── Helper ────────────────────────────────────────────────────────────


def _serialize_build(build) -> dict[str, Any]:
    """Convert a BuildJob ORM object to a serialisable dict."""
    return {
        "id": build.id,
        "migration_id": build.migration_id,
        "status": build.status if isinstance(build.status, str) else build.status.value,
        "build_tool": build.build_tool,
        "exit_code": build.exit_code,
        "build_log": build.build_log,
        "created_at": build.created_at.isoformat() if build.created_at else None,
        "completed_at": build.completed_at.isoformat() if build.completed_at else None,
        "duration_ms": build.duration_ms,
    }


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post(
    "/migrations/{migration_id}/builds",
    status_code=202,
    summary="Trigger a build",
    description="Start a Maven/Gradle build for a completed migration's generated project.",
    response_description="The created build job with status PENDING.",
)
async def create_build(
    migration_id: str = Path(..., description="Migration job ID."),
    body: BuildCreateRequest = BuildCreateRequest(),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    build = await BuildService.create_build(db, migration_id, body.build_tool)
    return JSONResponse(
        status_code=202,
        content=_serialize_build(build),
    )


@router.get(
    "/builds/{build_id}",
    summary="Get build details",
    description="Retrieve full details for a build job, including the console log.",
)
async def get_build(
    build_id: str = Path(..., description="Build job ID."),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    build = await BuildService.get_build(db, build_id)
    return JSONResponse(content=_serialize_build(build))


@router.get(
    "/migrations/{migration_id}/builds",
    summary="List builds for migration",
    description="Return all build jobs for a given migration, newest first.",
)
async def list_builds(
    migration_id: str = Path(..., description="Migration job ID."),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    builds = await BuildService.get_builds_for_migration(db, migration_id)
    return JSONResponse(content={
        "migration_id": migration_id,
        "builds": [_serialize_build(b) for b in builds],
        "total": len(builds),
    })
