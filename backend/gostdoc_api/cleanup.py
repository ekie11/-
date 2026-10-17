"""Очистка: удаляет файлы просроченных задач и просроченные сессии."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import storage
from .config import Settings
from .models import Job, SessionToken


def _aware(dt: datetime) -> datetime:
    # SQLite возвращает naive-даты; считаем их UTC (как в auth.py).
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def cleanup_expired(db: Session, settings: Settings, now: datetime) -> int:
    """Помечает просроченные задачи `expired`, удаляя файлы; возвращает число задач."""
    now = _aware(now)
    count = 0
    jobs = db.scalars(select(Job).where(Job.expires_at.is_not(None), Job.status != "expired"))
    for job in jobs:
        if _aware(job.expires_at) > now:
            continue
        storage.delete_job_files(settings, job.id)
        job.status = "expired"
        job.input_path = job.output_docx = job.output_pdf = None
        count += 1
    for token in db.scalars(select(SessionToken)):
        if _aware(token.expires_at) <= now:
            db.delete(token)
    db.commit()
    return count
