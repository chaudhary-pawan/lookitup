"""
celery_app.py — Celery application singleton.
All Celery tasks import `celery_app` from here.
"""

from celery import Celery
from backend.config import REDIS_URL

celery_app = Celery(
    "lookitup",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.ingestion.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,   # one task at a time per worker (ML is heavy)
)
