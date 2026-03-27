"""
GitHubService — async-friendly wrapper around the existing PyGithub integration.

Provides repository listing, creation, and file-push operations via the
GitHub Git Data API.  The token is passed per-call, never stored.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import structlog

from api.exceptions import AppException, ValidationError

logger = structlog.get_logger(__name__)

# Shared thread pool for blocking PyGithub calls
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="github")


class GitHubError(AppException):
    """GitHub API error."""

    status_code = 502
    error_code = "GITHUB_ERROR"

    def __init__(self, detail: str = "GitHub API request failed", **kwargs):
        super().__init__(detail=detail, **kwargs)


class GitHubService:
    """
    Async facade over the synchronous ``backend.services.github_service``
    module.  Each method runs blocking PyGithub calls in a thread pool so
    the event loop is never blocked.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_backend_service(token: str):
        """
        Instantiate the legacy backend GitHubService with the given token.

        Raises GitHubError if the import or instantiation fails.
        """
        try:
            from backend.services.github_service import (
                GitHubService as BackendGitHubService,
            )

            return BackendGitHubService(token)
        except ImportError:
            raise GitHubError(
                detail="GitHub integration backend is not available.",
            )
        except Exception as exc:
            raise GitHubError(detail=f"Failed to initialise GitHub client: {exc}")

    @staticmethod
    async def _run_in_thread(fn, *args, **kwargs) -> Any:
        """Run a blocking function in the shared thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))

    # ------------------------------------------------------------------
    # Push files
    # ------------------------------------------------------------------

    @staticmethod
    async def push_to_repo(
        token: str,
        repo_name: str,
        files: dict[str, str],
        commit_message: str = "Migration: push generated Spring Boot project",
        branch: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Push a set of files to a GitHub repository using the Git Data API.

        Args:
            token: GitHub personal access token.
            repo_name: Full repository name (``owner/repo``).
            files: Mapping of file paths to content strings.
            commit_message: Git commit message.
            branch: Target branch (defaults to repo default branch).

        Returns:
            Dict with commit sha, html_url, and files_pushed count.

        Raises:
            ValidationError: If required parameters are missing.
            GitHubError: If the push fails.
        """
        if not token:
            raise ValidationError(detail="GitHub token is required.")
        if not repo_name or "/" not in repo_name:
            raise ValidationError(
                detail="repo_name must be in 'owner/repo' format.",
            )
        if not files:
            raise ValidationError(detail="No files to push.")

        owner, name = repo_name.split("/", 1)
        svc = GitHubService._get_backend_service(token)

        try:
            result = await GitHubService._run_in_thread(
                svc.push_files,
                owner,
                name,
                files,
                branch,
                commit_message,
            )
            logger.info("github.push_success", repo=repo_name, files=len(files))
            return result
        except Exception as exc:
            logger.error("github.push_failed", repo=repo_name, error=str(exc))
            raise GitHubError(detail=f"Push to {repo_name} failed: {exc}")

    # ------------------------------------------------------------------
    # Create repository
    # ------------------------------------------------------------------

    @staticmethod
    async def create_repo(
        token: str,
        name: str,
        description: str = "",
        private: bool = True,
        org: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a new GitHub repository.

        Args:
            token: GitHub personal access token.
            name: Repository name.
            description: Repository description.
            private: Whether the repo should be private.
            org: Optional organisation under which to create.

        Returns:
            Dict with full_name, html_url, default_branch.
        """
        if not token:
            raise ValidationError(detail="GitHub token is required.")
        if not name:
            raise ValidationError(detail="Repository name is required.")

        svc = GitHubService._get_backend_service(token)

        try:
            result = await GitHubService._run_in_thread(
                svc.create_repo, name, description, private, org,
            )
            logger.info("github.repo_created", repo=result.get("full_name"))
            return result
        except Exception as exc:
            logger.error("github.repo_create_failed", name=name, error=str(exc))
            raise GitHubError(detail=f"Failed to create repository '{name}': {exc}")

    # ------------------------------------------------------------------
    # List repositories
    # ------------------------------------------------------------------

    @staticmethod
    async def list_repos(
        token: str,
        org: Optional[str] = None,
        sort: str = "updated",
    ) -> list[dict[str, Any]]:
        """
        List repositories for the authenticated user (or organisation).

        Args:
            token: GitHub personal access token.
            org: Optional organisation login to list repos for.
            sort: Sort field (``updated``, ``created``, ``pushed``).

        Returns:
            List of repo info dicts.
        """
        if not token:
            raise ValidationError(detail="GitHub token is required.")

        svc = GitHubService._get_backend_service(token)

        try:
            repos = await GitHubService._run_in_thread(
                svc.list_repos, org, sort,
            )
            return repos
        except Exception as exc:
            logger.error("github.list_repos_failed", error=str(exc))
            raise GitHubError(detail=f"Failed to list repositories: {exc}")

    # ------------------------------------------------------------------
    # Get repository info
    # ------------------------------------------------------------------

    @staticmethod
    async def get_repo_info(
        token: str,
        repo_name: str,
    ) -> dict[str, Any]:
        """
        Get detailed information about a single repository.

        Args:
            token: GitHub personal access token.
            repo_name: Full repository name (``owner/repo``).

        Returns:
            Dict with repository details.
        """
        if not token:
            raise ValidationError(detail="GitHub token is required.")
        if not repo_name or "/" not in repo_name:
            raise ValidationError(
                detail="repo_name must be in 'owner/repo' format.",
            )

        svc = GitHubService._get_backend_service(token)

        try:
            user_info = await GitHubService._run_in_thread(svc.get_user_info)
            repos = await GitHubService._run_in_thread(svc.list_repos)
            # Find the specific repo in the list
            for repo in repos:
                if repo["full_name"] == repo_name:
                    return repo
            raise GitHubError(
                detail=f"Repository '{repo_name}' not found or not accessible.",
            )
        except GitHubError:
            raise
        except Exception as exc:
            logger.error("github.get_repo_failed", repo=repo_name, error=str(exc))
            raise GitHubError(detail=f"Failed to get repository info: {exc}")
