"""Очистка: удаляет файлы просроченных задач и просроченные сессии."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from . import storage
from .config import Settings
from .llm import extraction_timeout_s
from .models import Extraction, GuestSession, Job, SessionToken


def _aware(dt: datetime) -> datetime:
    # SQLite возвращает naive-даты; считаем их UTC (как в auth.py).
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


STUCK_MIN = timedelta(minutes=30)
STUCK_QUEUE_SLACK = timedelta(minutes=10)  # ожидание в очереди одного воркера
STUCK_MESSAGE = "Сервис распознавания временно недоступен, попробуйте позже"


def stuck_after(settings: Settings) -> timedelta:
    """Через сколько извлечение считается зависшим: таймаут задачи плюс запас на очередь."""
    return max(STUCK_MIN, timedelta(seconds=extraction_timeout_s(settings)) + STUCK_QUEUE_SLACK)


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
    for guest in db.scalars(select(GuestSession)):
        if _aware(guest.expires_at) <= now:
            db.delete(guest)
    db.execute(
        update(Extraction)
        .where(
            Extraction.status.in_(("queued", "running")),
            Extraction.created_at < now - stuck_after(settings),
        )
        .values(status="failed", error=STUCK_MESSAGE, counts_toward_limit=False)
    )
    db.execute(
        delete(Extraction).where(
            Extraction.created_at < now - timedelta(days=settings.file_ttl_days)
        )
    )
    db.commit()
    return count
