"""
V2 GitHub endpoints — repository management and code push.

Routes:
  POST  /github/push   → Push migration output to a GitHub repo
  GET   /github/repos  → List user's repositories
  POST  /github/repos  → Create a new repository
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.exceptions import ValidationError
from api.services.github_service import GitHubService
from api.services.migration_service import MigrationService

router = APIRouter()


# ── Request / Response Schemas ────────────────────────────────────────


class GitHubPushRequest(BaseModel):
    """Payload for pushing migration output to GitHub."""

    migration_id: str = Field(..., description="Migration job ID whose output to push.")
    repo_name: str = Field(
        ..., description="Full repository name (owner/repo).",
    )
    branch: Optional[str] = Field(
        default=None, description="Target branch (defaults to repo default).",
    )
    commit_message: str = Field(
        default="Migration: push generated Spring Boot project",
        description="Git commit message.",
    )


class GitHubCreateRepoRequest(BaseModel):
    """Payload for creating a new GitHub repository."""

    name: str = Field(..., min_length=1, max_length=100, description="Repository name.")
    description: str = Field(default="", description="Repository description.")
    private: bool = Field(default=True, description="Create as private repo.")
    org: Optional[str] = Field(
        default=None, description="Organisation login (omit for personal repo).",
    )


# ── Helper ────────────────────────────────────────────────────────────


def _extract_token(authorization: Optional[str]) -> str:
    """
    Extract a GitHub token from the Authorization header.

    Accepts either ``Bearer <token>`` or ``token <token>`` formats.
    """
    if not authorization:
        raise ValidationError(
            detail="Authorization header with GitHub token is required.",
            errors=[{"field": "Authorization", "message": "Missing header."}],
        )
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() in ("bearer", "token"):
        return parts[1]
    # Accept raw token as well
    return authorization


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post(
    "/github/push",
    summary="Push to GitHub",
    description="Push a completed migration's generated files to a GitHub repository.",
)
async def push_to_github(
    body: GitHubPushRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    token = _extract_token(authorization)

    # Retrieve the migration's output files
    files = await MigrationService.get_migration_files(db, body.migration_id)

    # Try to create repo if it doesn't exist
    if "/" in body.repo_name:
        owner, name = body.repo_name.split("/", 1)
        try:
            await GitHubService.push_to_repo(
                token=token,
                repo_name=body.repo_name,
                files=files,
                commit_message=body.commit_message,
                branch=body.branch,
            )
        except Exception as first_err:
            if "404" in str(first_err) or "Not Found" in str(first_err):
                # Repo doesn't exist — create it first
                try:
                    await GitHubService.create_repo(
                        token=token,
                        name=name,
                        description=f"Spring Boot project migrated from MuleSoft",
                        private=True,
                    )
                except Exception:
                    pass  # Repo might already exist or creation failed
                # Retry push
                result = await GitHubService.push_to_repo(
                    token=token,
                    repo_name=body.repo_name,
                    files=files,
                    commit_message=body.commit_message,
                    branch=body.branch,
                )
                return JSONResponse(content={
                    "migration_id": body.migration_id,
                    "repo_name": body.repo_name,
                    "repo_created": True,
                    **result,
                })
            raise first_err

    result = await GitHubService.push_to_repo(
        token=token,
        repo_name=body.repo_name,
        files=files,
        commit_message=body.commit_message,
        branch=body.branch,
    )
    return JSONResponse(content={
        "migration_id": body.migration_id,
        "repo_name": body.repo_name,
        **result,
    })


@router.get(
    "/github/repos",
    summary="List repositories",
    description="List GitHub repositories for the authenticated user or organisation.",
)
async def list_repos(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    org: Optional[str] = Query(default=None, description="Organisation login."),
    sort: str = Query(default="updated", description="Sort field."),
) -> JSONResponse:
    token = _extract_token(authorization)
    repos = await GitHubService.list_repos(token=token, org=org, sort=sort)
    return JSONResponse(content={"repos": repos, "total": len(repos)})


@router.post(
    "/github/repos",
    status_code=201,
    summary="Create repository",
    description="Create a new GitHub repository for the authenticated user or organisation.",
)
async def create_repo(
    body: GitHubCreateRepoRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> JSONResponse:
    token = _extract_token(authorization)
    result = await GitHubService.create_repo(
        token=token,
        name=body.name,
        description=body.description,
        private=body.private,
        org=body.org,
    )
    return JSONResponse(status_code=201, content=result)
