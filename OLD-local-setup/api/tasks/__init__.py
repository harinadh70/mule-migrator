"""
Celery task definitions for asynchronous pipeline processing.

Exports the shared Celery application instance and all task modules
so that ``celery -A api.tasks worker`` discovers everything automatically.
"""

from api.tasks.celery_app import celery_app

__all__ = ["celery_app"]
