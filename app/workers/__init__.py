"""Celery workers package。對外暴露 celery_app,方便 `-A app.workers` 啟動。"""

from app.workers.celery_app import celery_app  # noqa: F401

__all__ = ["celery_app"]
