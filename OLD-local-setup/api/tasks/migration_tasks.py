"""
Celery tasks for running MuleSoft-to-SpringBoot migrations.

The main ``run_migration`` task loads a MigrationJob from the database,
builds an AgentContext, executes the PipelineOrchestrator, and streams
progress events to Redis pub/sub so connected WebSocket clients receive
real-time updates.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from api.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
#  Helpers — async bridge
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Run an async coroutine from synchronous Celery task context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
#  Database session helper (standalone, not FastAPI-managed)
# ---------------------------------------------------------------------------


async def _get_session():
    """Create a standalone async session for use inside Celery workers."""
    from api.database import _get_session_factory

    factory = _get_session_factory()
    return factory()


# ---------------------------------------------------------------------------
#  Redis pub/sub helper
# ---------------------------------------------------------------------------


async def _get_redis():
    """Create a standalone Redis connection for Celery workers."""
    import redis.asyncio as aioredis
    from api.config import get_settings

    settings = get_settings()
    return aioredis.from_url(
        settings.redis.url,
        decode_responses=True,
    )


async def _publish_event(migration_id: str, event: Dict[str, Any]) -> None:
    """Publish a migration event to the Redis channel."""
    import json

    redis = await _get_redis()
    try:
        channel = f"migration:{migration_id}:events"
        await redis.publish(channel, json.dumps(event))

        # Also store in a sorted set for replay on reconnection
        event_key = f"migration:{migration_id}:event_log"
        score = event.get("timestamp", time.time())
        await redis.zadd(event_key, {json.dumps(event): score})
        # Keep only last 500 events
        await redis.zremrangebyrank(event_key, 0, -501)
        # Expire event log after 24 hours
        await redis.expire(event_key, 86400)
    finally:
        await redis.close()


# ---------------------------------------------------------------------------
#  Progress callback factory
# ---------------------------------------------------------------------------


def _make_progress_callback(migration_id: str):
    """
    Return a callback compatible with PipelineOrchestrator's event system.

    The callback publishes each PipelineEvent to Redis so WebSocket clients
    receive real-time updates.
    """

    def callback(event) -> None:
        """Synchronous callback invoked by the orchestrator."""
        if hasattr(event, "to_dict"):
            event_data = event.to_dict()
        elif isinstance(event, dict):
            event_data = event
        else:
            event_data = {"raw": str(event)}

        event_data.setdefault("timestamp", time.time())
        event_data["migration_id"] = migration_id

        try:
            _run_async(_publish_event(migration_id, event_data))
        except Exception as exc:
            logger.warning(
                "migration.publish_event_failed",
                migration_id=migration_id,
                error=str(exc),
            )

    return callback


# ---------------------------------------------------------------------------
#  Task: run_migration
# ---------------------------------------------------------------------------


class MigrationTask(Task):
    """Custom base task with automatic retry on transient failures."""

    autoretry_for = (ConnectionError, OSError)
    retry_backoff = True
    retry_backoff_max = 120
    retry_jitter = True
    max_retries = 3


@celery_app.task(
    bind=True,
    base=MigrationTask,
    name="api.tasks.migration_tasks.run_migration",
    acks_late=True,
    reject_on_worker_lost=True,
    track_started=True,
)
def run_migration(self, migration_id: str) -> Dict[str, Any]:
    """
    Execute a full migration pipeline for the given MigrationJob.

    Args:
        migration_id: UUID of the MigrationJob row to process.

    Returns:
        A dict summary of the pipeline run: status, duration, tokens, cost.
    """
    logger.info(
        "migration.task_started",
        migration_id=migration_id,
        task_id=self.request.id,
        retry=self.request.retries,
    )

    try:
        result = _run_async(_execute_migration(self, migration_id))
        return result
    except SoftTimeLimitExceeded:
        logger.error(
            "migration.soft_timeout",
            migration_id=migration_id,
        )
        _run_async(_mark_migration_failed(
            migration_id,
            error="Task exceeded soft time limit (540s)",
        ))
        _run_async(_publish_event(migration_id, {
            "type": "migration_complete",
            "status": "timed_out",
            "migration_id": migration_id,
            "timestamp": time.time(),
        }))
        return {"status": "timed_out", "migration_id": migration_id}
    except Exception as exc:
        logger.error(
            "migration.task_error",
            migration_id=migration_id,
            error=str(exc),
            exc_info=True,
        )
        _run_async(_mark_migration_failed(migration_id, error=str(exc)))
        _run_async(_publish_event(migration_id, {
            "type": "migration_complete",
            "status": "failed",
            "error": str(exc),
            "migration_id": migration_id,
            "timestamp": time.time(),
        }))
        raise self.retry(exc=exc)


async def _execute_migration(task: Task, migration_id: str) -> Dict[str, Any]:
    """Core async logic for a migration run."""
    from api.agents.context import AgentContext
    from api.agents.orchestrator import PipelineOrchestrator, PipelineConfig
    from api.config import get_settings
    from api.models.migration import MigrationJob, MigrationStatus

    settings = get_settings()

    # ── Load the MigrationJob ──────────────────────────────────
    session = await _get_session()
    try:
        result = await session.execute(
            select(MigrationJob).where(MigrationJob.id == migration_id)
        )
        job: Optional[MigrationJob] = result.scalar_one_or_none()

        if job is None:
            raise ValueError(f"MigrationJob {migration_id} not found")

        if job.status == MigrationStatus.CANCELLED:
            logger.info("migration.already_cancelled", migration_id=migration_id)
            return {"status": "cancelled", "migration_id": migration_id}

        # Transition to RUNNING
        job.mark_running()
        await session.commit()
        await session.refresh(job)
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

    # ── Publish pipeline_started event ─────────────────────────
    await _publish_event(migration_id, {
        "type": "pipeline_started",
        "migration_id": migration_id,
        "project_name": job.project_name,
        "timestamp": time.time(),
    })

    # ── Build the AgentContext ─────────────────────────────────
    llm_config = job.llm_config or {
        "provider": settings.llm.default_provider,
        "model": settings.llm.default_model,
    }

    context = AgentContext(
        enabled=settings.agents_enabled,
        llm_config=llm_config,
        run_id=migration_id,
    )

    # Load XML files into context
    xml_files: Dict[str, str] = {}
    for file_entry in (job.input_xml_files or []):
        name = file_entry.get("name", "unknown.xml")
        content = file_entry.get("content", "")
        xml_files[name] = content
    context.set_artifact("xml_files", xml_files)

    # Load project config
    context.set_artifact("config", {
        "group_id": job.group_id or "com.example",
        "artifact_id": job.project_name or "migrated-app",
        "java_version": job.java_version or "17",
    })

    # Load DataWeave scripts if present
    if job.dataweave_scripts:
        context.set_artifact("dataweave_scripts", job.dataweave_scripts)

    # Check for cancellation before starting
    if _is_cancelled(task):
        await _mark_migration_cancelled(migration_id)
        return {"status": "cancelled", "migration_id": migration_id}

    start_time = time.monotonic()

    # ── Run static engine directly (reliable) ─────────────────
    generated_files: Dict[str, str] = {}
    agent_trace: Dict = {}
    errors: list = []

    try:
        from backend.migrator.parser import MuleSoftParser
        from backend.migrator.flow_converter import FlowConverter
        from backend.migrator.connector_mapper import ConnectorMapper
        from backend.migrator.dataweave_converter import DataWeaveConverter
        from backend.migrator.spring_generator import SpringBootGenerator

        parser = MuleSoftParser()
        mapper = ConnectorMapper()
        dw_converter = DataWeaveConverter()

        config = context.get_artifact("config") or {}
        group_id = config.get("group_id", "com.example")
        artifact_id = config.get("artifact_id", "migrated-app")
        java_version = config.get("java_version", "17")

        all_parsed = {}
        unknown_elements = []

        for filename, xml_content in xml_files.items():
            try:
                parsed = parser.parse(xml_content)
                if parsed is None:
                    continue
                all_parsed = parsed

                converter = FlowConverter(dw_converter, mapper)
                conversion_result = converter.convert(parsed, {})
                if isinstance(conversion_result, dict):
                    files_dict = conversion_result.get("files", {})
                    if not files_dict:
                        for k, v in conversion_result.items():
                            if isinstance(v, str) and ("." in k or "/" in k):
                                files_dict[k] = v
                    generated_files.update(files_dict)
                    unknown_elements.extend(conversion_result.get("unknown_elements", []))
            except Exception as exc:
                logger.warning("static_engine.file_failed", filename=filename, error=str(exc))
                errors.append(f"File {filename}: {str(exc)}")

        # Generate Spring project skeleton
        if all_parsed:
            try:
                generator = SpringBootGenerator(
                    project_name=artifact_id,
                    group_id=group_id,
                    java_version=java_version,
                )
                # Use ConnectorMapper to get proper dependencies
                connector_info = mapper.map_connectors(all_parsed)
                project_files = generator.generate(
                    generated_files,
                    connector_info,
                    all_parsed,
                )
                if isinstance(project_files, dict):
                    for k, v in project_files.items():
                        if isinstance(v, str):
                            generated_files[k] = v
            except Exception as exc:
                logger.warning("static_engine.generate_failed", error=str(exc))
                errors.append(f"Spring generation: {str(exc)}")

        logger.info("static_engine.complete", files=len(generated_files), migration_id=migration_id)

        agent_trace = {
            "status": "completed",
            "agents_executed": ["static_engine"],
            "agent_results": {
                "static_engine": {
                    "status": "success",
                    "files_generated": len(generated_files),
                    "unknown_elements": len(unknown_elements),
                }
            },
        }

    except Exception as exc:
        logger.error("static_engine.failed", error=str(exc), exc_info=True)
        errors.append(f"Static engine error: {str(exc)}")
        agent_trace = {"status": "failed", "error": str(exc)}

    # ── Optionally run LLM orchestrator for enhanced output ────
    report = None
    llm_enabled = (job.llm_config or {}).get("enabled", False)
    if llm_enabled and generated_files:
        try:
            progress_callback = _make_progress_callback(migration_id)
            pipeline_config = PipelineConfig(global_timeout_s=540)
            orchestrator = PipelineOrchestrator(
                llm_config=llm_config,
                pipeline_config=pipeline_config,
                event_callback=progress_callback,
            )
            context.set_artifact("generated_files", generated_files)
            report = await asyncio.wait_for(
                orchestrator.run_pipeline(context),
                timeout=120,
            )
            # Merge any LLM-enhanced files
            llm_files = context.get_artifact("generated_files") or {}
            generated_files.update(llm_files)
        except Exception as exc:
            logger.warning("llm_pipeline.failed", error=str(exc))

    duration_ms = int((time.monotonic() - start_time) * 1000)

    # ── Persist results back to the database ───────────────────
    session = await _get_session()
    try:
        result = await session.execute(
            select(MigrationJob).where(MigrationJob.id == migration_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise ValueError(f"MigrationJob {migration_id} disappeared during run")

        job.output_files = generated_files
        job.agent_trace = report.to_dict() if report and hasattr(report, "to_dict") else agent_trace
        job.total_tokens_used = report.total_tokens if report and hasattr(report, "total_tokens") else 0
        job.total_cost_usd = report.total_cost_usd if report and hasattr(report, "total_cost_usd") else 0.0
        job.duration_ms = duration_ms

        job.summary = {
            "agents_executed": agent_trace.get("agents_executed", ["static_engine"]),
            "status": "completed",
            "errors": errors,
            "total_files": len(generated_files),
        }

        job.mark_completed()
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

    # ── Publish completion event ───────────────────────────────
    final_status = "completed"
    await _publish_event(migration_id, {
        "type": "migration_complete",
        "status": final_status,
        "migration_id": migration_id,
        "duration_ms": duration_ms,
        "total_tokens": report.total_tokens if hasattr(report, "total_tokens") else 0,
        "total_cost_usd": report.total_cost_usd if hasattr(report, "total_cost_usd") else 0.0,
        "timestamp": time.time(),
    })

    logger.info(
        "migration.task_completed",
        migration_id=migration_id,
        status=final_status,
        duration_ms=duration_ms,
    )

    return {
        "status": final_status,
        "migration_id": migration_id,
        "duration_ms": duration_ms,
        "total_tokens": report.total_tokens if hasattr(report, "total_tokens") else 0,
    }


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _is_cancelled(task: Task) -> bool:
    """Check if the current task has been revoked."""
    return task.is_aborted() if hasattr(task, "is_aborted") else False


async def _mark_migration_failed(migration_id: str, error: str = "") -> None:
    """Update the MigrationJob status to FAILED."""
    from api.models.migration import MigrationJob

    session = await _get_session()
    try:
        result = await session.execute(
            select(MigrationJob).where(MigrationJob.id == migration_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.mark_failed()
            if error:
                job.summary = {**(job.summary or {}), "error": error}
            await session.commit()
    except Exception:
        await session.rollback()
    finally:
        await session.close()


async def _mark_migration_cancelled(migration_id: str) -> None:
    """Update the MigrationJob status to CANCELLED."""
    from api.models.migration import MigrationJob, MigrationStatus

    session = await _get_session()
    try:
        result = await session.execute(
            select(MigrationJob).where(MigrationJob.id == migration_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.status = MigrationStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()
    except Exception:
        await session.rollback()
    finally:
        await session.close()


# ---------------------------------------------------------------------------
#  Task: cancel_migration
# ---------------------------------------------------------------------------


@celery_app.task(
    name="api.tasks.migration_tasks.cancel_migration",
    ignore_result=False,
)
def cancel_migration(migration_id: str) -> Dict[str, Any]:
    """
    Cancel a running migration by revoking the Celery task and updating the DB.

    Args:
        migration_id: UUID of the MigrationJob to cancel.

    Returns:
        A dict indicating whether cancellation was successful.
    """
    logger.info("migration.cancel_requested", migration_id=migration_id)

    # Try to find and revoke the active task
    from celery.result import AsyncResult

    # Look up the task ID from Redis (stored when task starts)
    task_id = _run_async(_get_task_id_for_migration(migration_id))

    if task_id:
        result = AsyncResult(task_id, app=celery_app)
        result.revoke(terminate=True, signal="SIGTERM")
        logger.info(
            "migration.task_revoked",
            migration_id=migration_id,
            task_id=task_id,
        )

    # Update DB status
    _run_async(_mark_migration_cancelled(migration_id))

    # Notify WebSocket clients
    _run_async(_publish_event(migration_id, {
        "type": "migration_complete",
        "status": "cancelled",
        "migration_id": migration_id,
        "timestamp": time.time(),
    }))

    return {
        "status": "cancelled",
        "migration_id": migration_id,
        "task_revoked": task_id is not None,
    }


async def _get_task_id_for_migration(migration_id: str) -> Optional[str]:
    """Look up the Celery task ID associated with a migration from Redis."""
    redis = await _get_redis()
    try:
        task_id = await redis.get(f"migration:{migration_id}:task_id")
        return task_id
    finally:
        await redis.close()
