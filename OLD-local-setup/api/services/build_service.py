"""
BuildService — business logic for Maven/Gradle build job lifecycle.

Manages creation, retrieval, log streaming, and status updates for
build jobs associated with completed migrations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.exceptions import MigrationError, NotFoundError, ValidationError
from api.models.build import BuildJob, BuildStatus
from api.models.migration import MigrationJob, MigrationStatus

logger = structlog.get_logger(__name__)


class BuildService:
    """Stateless service for build job operations."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @staticmethod
    async def create_build(
        db: AsyncSession,
        migration_id: str,
        build_tool: str = "maven",
    ) -> BuildJob:
        """
        Create a new build job for a completed migration and enqueue it.

        Args:
            db: Active database session.
            migration_id: The migration whose output should be built.
            build_tool: Build system to use (``maven`` or ``gradle``).

        Returns:
            The newly created BuildJob (status=PENDING).

        Raises:
            NotFoundError: If the migration does not exist.
            ValidationError: If the migration has no output files.
        """
        # -- Validate migration ------------------------------------------
        stmt = select(MigrationJob).where(
            MigrationJob.id == migration_id,
            MigrationJob.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        migration = result.scalar_one_or_none()

        if migration is None:
            raise NotFoundError(resource="MigrationJob", identifier=migration_id)

        if not migration.output_files:
            raise ValidationError(
                detail="Migration has no output files to build. Wait for migration to complete.",
                errors=[{
                    "field": "migration_id",
                    "message": "No output files available.",
                }],
            )

        # -- Create build job --------------------------------------------
        build = BuildJob(
            migration_id=migration_id,
            build_tool=build_tool,
            status=BuildStatus.PENDING,
        )
        db.add(build)
        await db.flush()

        # -- Enqueue Celery task -----------------------------------------
        try:
            from api.tasks.build_tasks import run_build

            run_build.delay(str(build.id), str(migration_id))
            logger.info("build.enqueued", build_id=build.id, migration_id=migration_id)
        except Exception as exc:
            logger.warning(
                "build.celery_enqueue_failed",
                build_id=build.id,
                error=str(exc),
            )

        return build

    # ------------------------------------------------------------------
    # Read — single
    # ------------------------------------------------------------------

    @staticmethod
    async def get_build(
        db: AsyncSession,
        build_id: str,
    ) -> BuildJob:
        """
        Fetch a single build job by ID.

        Raises:
            NotFoundError: If the build does not exist.
        """
        stmt = select(BuildJob).where(BuildJob.id == build_id)
        result = await db.execute(stmt)
        build = result.scalar_one_or_none()
        if build is None:
            raise NotFoundError(resource="BuildJob", identifier=build_id)
        return build

    # ------------------------------------------------------------------
    # Read — list for migration
    # ------------------------------------------------------------------

    @staticmethod
    async def get_builds_for_migration(
        db: AsyncSession,
        migration_id: str,
    ) -> list[BuildJob]:
        """
        Return all build jobs for a given migration, newest first.

        Raises:
            NotFoundError: If the migration does not exist.
        """
        # Verify migration exists
        mig_stmt = select(MigrationJob.id).where(
            MigrationJob.id == migration_id,
            MigrationJob.deleted_at.is_(None),
        )
        mig_result = await db.execute(mig_stmt)
        if mig_result.scalar_one_or_none() is None:
            raise NotFoundError(resource="MigrationJob", identifier=migration_id)

        stmt = (
            select(BuildJob)
            .where(BuildJob.migration_id == migration_id)
            .order_by(BuildJob.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Log streaming
    # ------------------------------------------------------------------

    @staticmethod
    async def append_build_log(
        db: AsyncSession,
        build_id: str,
        line: str,
    ) -> BuildJob:
        """
        Append a line to the build's console log.

        This is typically called from the Celery worker as the Maven
        process produces output.

        Raises:
            NotFoundError: If the build does not exist.
        """
        build = await BuildService.get_build(db, build_id)
        if build.build_log is None:
            build.build_log = ""
        build.build_log += line + "\n"
        return build

    # ------------------------------------------------------------------
    # Status update
    # ------------------------------------------------------------------

    @staticmethod
    async def update_build_status(
        db: AsyncSession,
        build_id: str,
        status: str,
        exit_code: Optional[int] = None,
    ) -> BuildJob:
        """
        Update the build status and optionally set the exit code.

        Args:
            db: Active database session.
            build_id: ID of the build to update.
            status: New status string (must match ``BuildStatus`` values).
            exit_code: Process exit code (set on completion/failure).

        Raises:
            NotFoundError: If the build does not exist.
            ValidationError: If the status value is invalid.
        """
        build = await BuildService.get_build(db, build_id)

        # Validate the status value
        try:
            new_status = BuildStatus(status)
        except ValueError:
            valid = [s.value for s in BuildStatus]
            raise ValidationError(
                detail=f"Invalid build status '{status}'. Must be one of: {valid}",
                errors=[{"field": "status", "message": f"Invalid value: {status}"}],
            )

        build.status = new_status

        if exit_code is not None:
            build.exit_code = exit_code

        if new_status in (BuildStatus.COMPLETED, BuildStatus.FAILED):
            build.completed_at = datetime.now(timezone.utc)
            if build.created_at:
                delta = build.completed_at - build.created_at
                build.duration_ms = int(delta.total_seconds() * 1000)

        logger.info(
            "build.status_updated",
            build_id=build_id,
            status=new_status.value,
            exit_code=exit_code,
        )
        return build
