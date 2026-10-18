"""Файловое хранилище задач: STORAGE_DIR/jobs/<job_id>/ с фиксированными именами файлов."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from gostdoc_api.config import Settings


def _job_path(settings: Settings, job_id: str) -> Path:
    try:
        parsed = uuid.UUID(job_id, version=4)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Некорректный id задачи: {job_id!r}") from exc
    # uuid.UUID(..., version=4) приводит биты версии; канонична только точная строка.
    if str(parsed) != job_id:
        raise ValueError(f"Некорректный id задачи: {job_id!r}")
    return Path(settings.storage_dir) / "jobs" / job_id


def job_dir(settings: Settings, job_id: str) -> Path:
    """Каталог файлов задачи; создаётся при первом обращении."""
    path = _job_path(settings, job_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def delete_job_files(settings: Settings, job_id: str) -> None:
    """Удаляет каталог задачи вместе с файлами; отсутствующий каталог — не ошибка."""
    shutil.rmtree(_job_path(settings, job_id), ignore_errors=True)
