"""Celery application.

Run with ``celery -A app.worker.celery_app worker``. Task implementations and
the event wiring (order created, stop delivered) are added in a later task
(see PROJECT_SPEC.md section 11); this module only defines the app so the
``worker`` service can boot.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "batna_water",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)

# Import task modules so Celery registers them once they exist.
celery_app.autodiscover_tasks(["app"])
