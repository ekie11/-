"""Очистка: удаляет файлы просроченных задач и просроченные сессии."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from . import storage
from .config import Settings
from .llm import extraction_timeout_s
from .models import Extraction, GuestSession, Job, SessionToken


def _aware(dt: datetime) -> datetime:
    # SQLite возвращает naive-даты; считаем их UTC (как в auth.py).
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


QUEUED_MAX_AGE = timedelta(hours=24)  # столько задача может ждать в очереди (ttl в RQ)
RUNNING_SLACK = timedelta(minutes=5)
STUCK_MESSAGE = "Сервис распознавания временно недоступен, попробуйте позже"


def running_stuck_after(settings: Settings) -> timedelta:
    """Сколько running-извлечение может идти: таймаут задачи плюс запас."""
    return timedelta(seconds=extraction_timeout_s(settings)) + RUNNING_SLACK


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
    stuck = or_(
        and_(
            Extraction.status == "running",
            Extraction.started_at.is_not(None),
            Extraction.started_at < now - running_stuck_after(settings),
        ),
        and_(Extraction.status == "queued", Extraction.created_at < now - QUEUED_MAX_AGE),
    )
    db.execute(
        update(Extraction)
        .where(stuck)
        .values(status="failed", error=STUCK_MESSAGE, counts_toward_limit=False)
    )
    db.execute(
        delete(Extraction).where(
            Extraction.created_at < now - timedelta(days=settings.file_ttl_days)
        )
    )
    db.commit()
    return count
