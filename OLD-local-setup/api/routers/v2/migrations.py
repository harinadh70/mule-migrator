"""
V2 Migration endpoints — full async lifecycle with Celery-backed processing.

Routes:
  POST   /migrations          → Create and enqueue migration (202)
  GET    /migrations           → Paginated list
  GET    /migrations/stats     → Aggregate statistics
  GET    /migrations/{id}      → Full details with agent traces
  GET    /migrations/{id}/files         → Generated output files
  GET    /migrations/{id}/files/{path}  → Single file content
  GET    /migrations/{id}/agents        → Agent pipeline status
  DELETE /migrations/{id}      → Soft delete
  POST   /migrations/{id}/cancel → Cancel running migration
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Path
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.services.migration_service import MigrationService

router = APIRouter()


# ── Request / Response Schemas ────────────────────────────────────────


class MigrationCreateRequest(BaseModel):
    """Payload for creating a new migration job."""

    project_name: str = Field(..., min_length=1, max_length=255, description="Spring Boot project name.")
    group_id: str = Field(default="com.example", max_length=255, description="Maven group ID.")
    java_version: str = Field(default="17", description="Target Java version.")
    input_xml_files: list[dict[str, Any]] = Field(
        ..., min_length=1, description="List of MuleSoft XML files [{name, content}].",
    )
    dataweave_scripts: Optional[dict[str, Any]] = Field(
        default=None, description="Optional DataWeave scripts {name: content}.",
    )
    llm_config: Optional[dict[str, Any]] = Field(
        default=None, description="LLM provider config {provider, model, enabled}.",
    )


class MigrationSummaryResponse(BaseModel):
    """Lightweight migration info for list views."""

    id: str
    project_name: str
    status: str
    created_at: str
    duration_ms: Optional[int] = None
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0

    class Config:
        from_attributes = True


class PaginatedMigrationResponse(BaseModel):
    """Paginated list of migrations."""

    items: list[MigrationSummaryResponse]
    total: int
    page: int
    size: int
    pages: int


class MigrationDetailResponse(BaseModel):
    """Full migration details."""

    id: str
    project_name: str
    group_id: str
    java_version: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    summary: Optional[dict[str, Any]] = None
    llm_validation: Optional[dict[str, Any]] = None
    agent_trace: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True


class MigrationStatsResponse(BaseModel):
    """Aggregate migration statistics."""

    total: int
    by_status: dict[str, int]
    avg_duration_ms: Optional[float] = None
    total_tokens_used: int
    total_cost_usd: float


# ── Helper ────────────────────────────────────────────────────────────


def _serialize_migration(job) -> dict[str, Any]:
    """Convert a MigrationJob ORM object to a serialisable dict."""
    return {
        "id": job.id,
        "project_name": job.project_name,
        "group_id": job.group_id,
        "java_version": job.java_version,
        "status": job.status if isinstance(job.status, str) else job.status.value,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "duration_ms": job.duration_ms,
        "total_tokens_used": job.total_tokens_used or 0,
        "total_cost_usd": job.total_cost_usd or 0.0,
        "output_files": job.output_files,
        "summary": job.summary,
        "llm_validation": job.llm_validation,
        "agent_trace": job.agent_trace,
    }


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post(
    "/migrations",
    status_code=202,
    summary="Create a new migration",
    description="Submit a MuleSoft project for migration. Returns immediately with a job ID; processing happens asynchronously via Celery.",
    response_description="The created migration job with status QUEUED.",
)
async def create_migration(
    body: MigrationCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    job = await MigrationService.create_migration(db, body.model_dump())
    return JSONResponse(
        status_code=202,
        content=_serialize_migration(job),
    )


@router.get(
    "/migrations",
    summary="List migrations",
    description="Retrieve a paginated list of migration jobs, optionally filtered by status.",
)
async def list_migrations(
    page: int = Query(default=1, ge=1, description="Page number."),
    size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="Items per page."),
    status: Optional[str] = Query(default=None, description="Filter by status."),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await MigrationService.list_migrations(db, page, size, status)
    items = [
        {
            "id": j.id,
            "project_name": j.project_name,
            "status": j.status if isinstance(j.status, str) else j.status.value,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "duration_ms": j.duration_ms,
            "total_tokens_used": j.total_tokens_used or 0,
            "total_cost_usd": j.total_cost_usd or 0.0,
        }
        for j in result["items"]
    ]
    return JSONResponse(content={
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "size": result["size"],
        "pages": result["pages"],
    })


@router.get(
    "/migrations/stats",
    summary="Migration statistics",
    description="Aggregate statistics across all migration jobs.",
)
async def migration_stats(
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    stats = await MigrationService.get_migration_stats(db)
    return JSONResponse(content=stats)


@router.get(
    "/migrations/{migration_id}",
    summary="Get migration details",
    description="Retrieve full details for a single migration, including agent traces.",
)
async def get_migration(
    migration_id: str = Path(..., description="Migration job ID."),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    job = await MigrationService.get_migration(db, migration_id)
    return JSONResponse(content=_serialize_migration(job))


@router.get(
    "/migrations/{migration_id}/files",
    summary="Get migration output files",
    description="Return the dict of generated Spring Boot files for a completed migration.",
)
async def get_migration_files(
    migration_id: str = Path(..., description="Migration job ID."),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    job = await MigrationService.get_migration(db, migration_id)
    files = job.output_files or {}

    # Also extract files from agent_trace results if output_files is empty
    if not files:
        agent_trace = job.agent_trace or {}
        agent_results = agent_trace.get("agent_results", {})
        for agent_name, result in agent_results.items():
            output = result.get("output", {})
            if isinstance(output, dict):
                # docs agent stores files in output.docs
                docs = output.get("docs", {})
                if isinstance(docs, dict):
                    files.update(docs)
                # coder agent stores files in output.files
                code_files = output.get("files", {})
                if isinstance(code_files, dict):
                    files.update(code_files)

    return JSONResponse(content={
        "migration_id": migration_id,
        "files": {path: content for path, content in files.items()},
        "total_files": len(files),
    })


@router.get(
    "/migrations/{migration_id}/files/{file_path:path}",
    summary="Get single file content",
    description="Return the content of a single generated file.",
)
async def get_migration_file(
    migration_id: str = Path(..., description="Migration job ID."),
    file_path: str = Path(..., description="File path within the generated project."),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    # Reuse the files endpoint logic to get all files including agent outputs
    job = await MigrationService.get_migration(db, migration_id)
    files = job.output_files or {}
    if not files:
        agent_trace = job.agent_trace or {}
        for result in agent_trace.get("agent_results", {}).values():
            output = result.get("output", {})
            if isinstance(output, dict):
                files.update(output.get("docs", {}))
                files.update(output.get("files", {}))
    if file_path not in files:
        from api.exceptions import NotFoundError
        raise NotFoundError(resource="File", identifier=file_path)
    return PlainTextResponse(content=files[file_path], media_type="text/plain")


@router.get(
    "/migrations/{migration_id}/agents",
    summary="Get agent pipeline status",
    description="Return the agent trace data showing each agent's status, timing, and token usage.",
)
async def get_migration_agents(
    migration_id: str = Path(..., description="Migration job ID."),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    job = await MigrationService.get_migration(db, migration_id)

    # Build agent traces from JSONB agent_trace field or DB relationship
    traces = []

    # First try the JSONB agent_trace.agent_results (from Celery pipeline)
    agent_trace_data = job.agent_trace or {}
    agent_results = agent_trace_data.get("agent_results", {})
    if agent_results:
        for agent_name, result in agent_results.items():
            traces.append({
                "id": agent_name,
                "agent_name": agent_name,
                "status": "completed" if result.get("status") == "success" else result.get("status", "unknown"),
                "started_at": None,
                "completed_at": None,
                "duration_ms": result.get("duration_ms"),
                "token_usage": result.get("token_usage", 0),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "rag_results_used": result.get("rag_results_used", 0),
                "error": result.get("error"),
                "fallback_used": result.get("fallback_used", False),
                "output_summary": None,
            })
    # Fallback: try DB relationship
    elif hasattr(job, "agent_traces") and job.agent_traces:
        for trace in job.agent_traces:
            traces.append({
                "id": str(trace.id),
                "agent_name": trace.agent_name,
                "status": trace.status,
                "started_at": trace.started_at.isoformat() if trace.started_at else None,
                "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
                "duration_ms": trace.duration_ms,
                "token_usage": trace.token_usage,
                "prompt_tokens": trace.prompt_tokens,
                "completion_tokens": trace.completion_tokens,
                "rag_results_used": trace.rag_results_used,
                "error": trace.error,
                "fallback_used": trace.fallback_used,
                "output_summary": trace.output_summary,
            })

    return JSONResponse(content={
        "migration_id": migration_id,
        "status": job.status if isinstance(job.status, str) else job.status.value,
        "agents": traces,
    })


@router.delete(
    "/migrations/{migration_id}",
    summary="Delete migration",
    description="Soft-delete a migration job. The data is retained but hidden from list queries.",
)
async def delete_migration(
    migration_id: str = Path(..., description="Migration job ID."),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await MigrationService.delete_migration(db, migration_id)
    return JSONResponse(content={"id": migration_id, "deleted": True})


@router.post(
    "/migrations/{migration_id}/cancel",
    summary="Cancel migration",
    description="Cancel a running or queued migration and revoke the Celery task.",
)
async def cancel_migration(
    migration_id: str = Path(..., description="Migration job ID."),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    job = await MigrationService.cancel_migration(db, migration_id)
    return JSONResponse(content={
        "id": job.id,
        "status": job.status if isinstance(job.status, str) else job.status.value,
        "cancelled": True,
    })
