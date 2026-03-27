"""
Celery application factory and configuration.

Redis serves as both broker and result backend.  Tasks are routed to
dedicated queues (migration, build, indexing) so workers can be scaled
independently per workload type.

Usage::

    # Start a migration worker
    celery -A api.tasks worker -Q migration -c 2 --loglevel=info

    # Start a build worker
    celery -A api.tasks worker -Q build -c 4 --loglevel=info

    # Start the beat scheduler (periodic tasks)
    celery -A api.tasks beat --loglevel=info
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    after_setup_logger,
    after_setup_task_logger,
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
)
from kombu import Exchange, Queue

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
#  Broker / backend URLs (fall back to env vars, then defaults)
# ---------------------------------------------------------------------------

_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# ---------------------------------------------------------------------------
#  Celery application
# ---------------------------------------------------------------------------

celery_app = Celery(
    "migrator",
    broker=_BROKER_URL,
    backend=_RESULT_BACKEND,
)

# ---------------------------------------------------------------------------
#  Exchanges & Queues
# ---------------------------------------------------------------------------

_default_exchange = Exchange("default", type="direct")
_migration_exchange = Exchange("migration", type="direct")
_build_exchange = Exchange("build", type="direct")
_indexing_exchange = Exchange("indexing", type="direct")

celery_app.conf.task_queues = (
    Queue("default", _default_exchange, routing_key="default"),
    Queue("migration", _migration_exchange, routing_key="migration"),
    Queue("build", _build_exchange, routing_key="build"),
    Queue("indexing", _indexing_exchange, routing_key="indexing"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

# ---------------------------------------------------------------------------
#  Task routing
# ---------------------------------------------------------------------------

celery_app.conf.task_routes = {
    "api.tasks.migration_tasks.*": {"queue": "migration"},
    "api.tasks.build_tasks.*": {"queue": "build"},
    "api.tasks.indexing_tasks.*": {"queue": "indexing"},
}

# ---------------------------------------------------------------------------
#  Serialization — JSON only (no pickle for security)
# ---------------------------------------------------------------------------

celery_app.conf.accept_content = ["json"]
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.result_expires = 60 * 60 * 24  # 24 hours

# ---------------------------------------------------------------------------
#  Timeouts & rate limits
# ---------------------------------------------------------------------------

celery_app.conf.task_soft_time_limit = 540       # 9 min soft (for cleanup)
celery_app.conf.task_time_limit = 600            # 10 min hard kill
celery_app.conf.task_annotations = {
    "api.tasks.migration_tasks.run_migration": {
        "time_limit": 600,
        "soft_time_limit": 540,
        "rate_limit": "10/m",
    },
    "api.tasks.build_tasks.run_build": {
        "time_limit": 300,
        "soft_time_limit": 270,
        "rate_limit": "20/m",
    },
    "api.tasks.indexing_tasks.index_knowledge_base": {
        "time_limit": 600,
        "soft_time_limit": 540,
    },
    "api.tasks.indexing_tasks.cleanup_old_migrations": {
        "time_limit": 120,
        "soft_time_limit": 90,
    },
}

# ---------------------------------------------------------------------------
#  Retry defaults
# ---------------------------------------------------------------------------

celery_app.conf.task_default_retry_delay = 10          # 10 s first retry
celery_app.conf.task_max_retries = 3

# ---------------------------------------------------------------------------
#  Concurrency & prefetch
# ---------------------------------------------------------------------------

celery_app.conf.worker_prefetch_multiplier = 1         # one at a time per slot
celery_app.conf.worker_max_tasks_per_child = 50        # recycle after 50 tasks
celery_app.conf.worker_max_memory_per_child = 512_000  # 512 MB then recycle

# ---------------------------------------------------------------------------
#  Beat schedule (periodic tasks)
# ---------------------------------------------------------------------------

celery_app.conf.beat_schedule = {
    "daily-reindex-knowledge": {
        "task": "api.tasks.indexing_tasks.index_knowledge_base",
        "schedule": crontab(hour=2, minute=0),  # 02:00 UTC daily
        "options": {"queue": "indexing"},
    },
    "weekly-cleanup-old-migrations": {
        "task": "api.tasks.indexing_tasks.cleanup_old_migrations",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 03:00
        "args": (30,),
        "options": {"queue": "indexing"},
    },
}

celery_app.conf.timezone = "UTC"

# ---------------------------------------------------------------------------
#  Auto-discover task modules
# ---------------------------------------------------------------------------

celery_app.autodiscover_tasks(
    [
        "api.tasks.migration_tasks",
        "api.tasks.build_tasks",
        "api.tasks.indexing_tasks",
    ],
)

# ---------------------------------------------------------------------------
#  Structlog integration via Celery signals
# ---------------------------------------------------------------------------


@after_setup_logger.connect
def _setup_structlog_logger(logger=None, **kwargs):
    """Replace Celery's default logger configuration with structlog."""
    import logging

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@task_prerun.connect
def _task_prerun(sender=None, task_id=None, task=None, args=None, **kwargs):
    """Bind structlog context vars at the start of every task."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        celery_task_name=sender.name if sender else "unknown",
        celery_task_id=task_id or "unknown",
    )
    logger.info(
        "celery.task_started",
        task_name=sender.name if sender else "unknown",
        task_id=task_id,
    )


@task_postrun.connect
def _task_postrun(sender=None, task_id=None, state=None, **kwargs):
    """Log task completion."""
    logger.info(
        "celery.task_completed",
        task_name=sender.name if sender else "unknown",
        task_id=task_id,
        state=state,
    )
    structlog.contextvars.clear_contextvars()


@task_failure.connect
def _task_failure(sender=None, task_id=None, exception=None, traceback=None, **kwargs):
    """Log task failures."""
    logger.error(
        "celery.task_failed",
        task_name=sender.name if sender else "unknown",
        task_id=task_id,
        error=str(exception),
    )


@task_retry.connect
def _task_retry(sender=None, request=None, reason=None, **kwargs):
    """Log task retries."""
    logger.warning(
        "celery.task_retry",
        task_name=sender.name if sender else "unknown",
        task_id=request.id if request else "unknown",
        reason=str(reason),
    )
