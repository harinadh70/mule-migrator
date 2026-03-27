"""
MigrationService — business logic for migration job lifecycle.

Handles creation, retrieval, pagination, cancellation, soft-delete,
file access, and aggregate statistics.  Enqueues Celery tasks for
asynchronous pipeline execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.exceptions import NotFoundError, ValidationError, MigrationError
from api.models.migration import MigrationJob, MigrationStatus

logger = structlog.get_logger(__name__)


class MigrationService:
    """Stateless service — all state lives in the database."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @staticmethod
    async def create_migration(
        db: AsyncSession,
        data: dict[str, Any],
    ) -> MigrationJob:
        """
        Validate input, persist a new MigrationJob, and enqueue the
        Celery migration task.

        Args:
            db: Active database session.
            data: Request payload containing project_name, group_id,
                  input_xml_files, dataweave_scripts, llm_config, etc.

        Returns:
            The newly created MigrationJob (status=QUEUED).

        Raises:
            ValidationError: If required fields are missing or invalid.
        """
        # -- Validate required fields ------------------------------------
        project_name = data.get("project_name") or data.get("projectName")
        if not project_name:
            raise ValidationError(
                detail="project_name is required.",
                errors=[{"field": "project_name", "message": "This field is required."}],
            )

        xml_files = data.get("input_xml_files") or data.get("muleXmlFiles") or []
        single_xml = data.get("mule_xml") or data.get("muleXml") or ""
        if not xml_files and single_xml.strip():
            xml_files = [{"name": "main.xml", "content": single_xml}]

        if not xml_files:
            raise ValidationError(
                detail="At least one MuleSoft XML file is required.",
                errors=[{"field": "input_xml_files", "message": "No XML files provided."}],
            )

        # -- Build the ORM object ----------------------------------------
        job = MigrationJob(
            project_name=project_name,
            group_id=data.get("group_id") or data.get("groupId") or "com.example",
            java_version=data.get("java_version") or data.get("javaVersion") or "17",
            input_xml_files=xml_files,
            dataweave_scripts=data.get("dataweave_scripts") or data.get("dataweaveScripts") or {},
            llm_config=data.get("llm_config") or data.get("llmConfig") or {},
            status=MigrationStatus.QUEUED,
        )
        db.add(job)
        await db.flush()  # Ensure job.id is assigned

        # -- Enqueue Celery task -----------------------------------------
        try:
            from api.tasks.migration_tasks import run_migration

            run_migration.delay(str(job.id))
            logger.info("migration.enqueued", job_id=job.id)
        except Exception as exc:
            logger.warning(
                "migration.celery_enqueue_failed",
                job_id=job.id,
                error=str(exc),
            )
            # The job is persisted; a retry mechanism can pick it up later.

        return job

    # ------------------------------------------------------------------
    # Read — single
    # ------------------------------------------------------------------

    @staticmethod
    async def get_migration(
        db: AsyncSession,
        migration_id: str,
    ) -> MigrationJob:
        """
        Fetch a migration job by ID, including its agent traces.

        Raises:
            NotFoundError: If the job does not exist or is soft-deleted.
        """
        stmt = (
            select(MigrationJob)
            .where(
                MigrationJob.id == migration_id,
                MigrationJob.deleted_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            raise NotFoundError(resource="MigrationJob", identifier=migration_id)
        return job

    # ------------------------------------------------------------------
    # Read — list (paginated)
    # ------------------------------------------------------------------

    @staticmethod
    async def list_migrations(
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        status_filter: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Return a paginated list of migration jobs.

        Returns:
            Dict with ``items``, ``total``, ``page``, ``size``, ``pages``.
        """
        base = select(MigrationJob).where(MigrationJob.deleted_at.is_(None))

        if status_filter:
            base = base.where(MigrationJob.status == status_filter)

        # -- Total count -------------------------------------------------
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        # -- Paginated results -------------------------------------------
        offset = (page - 1) * size
        data_stmt = (
            base
            .order_by(MigrationJob.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        result = await db.execute(data_stmt)
        items = list(result.scalars().all())

        pages = max(1, (total + size - 1) // size)

        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        }

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    @staticmethod
    async def cancel_migration(
        db: AsyncSession,
        migration_id: str,
    ) -> MigrationJob:
        """
        Cancel a running or queued migration and revoke the Celery task.

        Raises:
            NotFoundError: If not found.
            MigrationError: If the job is not in a cancellable state.
        """
        job = await MigrationService.get_migration(db, migration_id)

        if job.status not in (
            MigrationStatus.PENDING,
            MigrationStatus.QUEUED,
            MigrationStatus.RUNNING,
        ):
            raise MigrationError(
                detail=f"Cannot cancel migration in '{job.status}' state.",
                project_id=migration_id,
            )

        job.status = MigrationStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        if job.started_at:
            delta = job.completed_at - job.started_at
            job.duration_ms = int(delta.total_seconds() * 1000)

        # -- Attempt Celery task revocation ------------------------------
        try:
            from api.tasks.migration_tasks import celery_app

            celery_app.control.revoke(migration_id, terminate=True)
            logger.info("migration.revoked", job_id=migration_id)
        except Exception as exc:
            logger.warning(
                "migration.revoke_failed",
                job_id=migration_id,
                error=str(exc),
            )

        return job

    # ------------------------------------------------------------------
    # Delete (soft)
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_migration(
        db: AsyncSession,
        migration_id: str,
    ) -> MigrationJob:
        """
        Soft-delete a migration job.

        Raises:
            NotFoundError: If not found.
        """
        job = await MigrationService.get_migration(db, migration_id)
        job.soft_delete()
        return job

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    @staticmethod
    async def get_migration_files(
        db: AsyncSession,
        migration_id: str,
    ) -> dict[str, Any]:
        """
        Return the generated output files dict for a completed migration.

        Raises:
            NotFoundError: If the job does not exist.
            MigrationError: If no output files are available yet.
        """
        job = await MigrationService.get_migration(db, migration_id)
        if not job.output_files:
            raise MigrationError(
                detail="No output files available. Migration may still be in progress.",
                project_id=migration_id,
            )
        return job.output_files

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @staticmethod
    async def get_migration_stats(db: AsyncSession) -> dict[str, Any]:
        """
        Compute aggregate statistics across all non-deleted migration jobs.

        Returns:
            Dict with total, by_status breakdown, avg_duration_ms,
            total_tokens_used, and total_cost_usd.
        """
        base = select(MigrationJob).where(MigrationJob.deleted_at.is_(None))

        # -- Total count -------------------------------------------------
        total = (
            await db.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar() or 0

        # -- Count by status ---------------------------------------------
        status_stmt = (
            select(
                MigrationJob.status,
                func.count().label("count"),
            )
            .where(MigrationJob.deleted_at.is_(None))
            .group_by(MigrationJob.status)
        )
        status_rows = (await db.execute(status_stmt)).all()
        by_status = {
            (row.status.value if hasattr(row.status, "value") else str(row.status)): row.count
            for row in status_rows
        }

        # -- Average duration (completed jobs only) ----------------------
        avg_duration = (
            await db.execute(
                select(func.avg(MigrationJob.duration_ms))
                .where(
                    MigrationJob.deleted_at.is_(None),
                    MigrationJob.status == MigrationStatus.COMPLETED,
                    MigrationJob.duration_ms.isnot(None),
                )
            )
        ).scalar()

        # -- Token and cost totals ---------------------------------------
        totals_stmt = select(
            func.coalesce(func.sum(MigrationJob.total_tokens_used), 0),
            func.coalesce(func.sum(MigrationJob.total_cost_usd), 0.0),
        ).where(MigrationJob.deleted_at.is_(None))
        totals_row = (await db.execute(totals_stmt)).one()

        return {
            "total": total,
            "by_status": by_status,
            "avg_duration_ms": float(round(avg_duration, 2)) if avg_duration else None,
            "total_tokens_used": int(totals_row[0]),
            "total_cost_usd": float(round(float(totals_row[1]), 4)),
        }
