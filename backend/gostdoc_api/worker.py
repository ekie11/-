"""Воркер: выполняет задачу обработки по снимку профиля."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from rq.timeouts import JobTimeoutException
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from gostdoc_engine.importer import InputError
from gostdoc_engine.pipeline import process
from gostdoc_engine.profile import Profile
from gostdoc_engine.textguard import TextChangedError

from . import storage
from .config import Settings, get_settings
from .db import make_engine, make_sessionmaker
from .models import Job
from .pdf import render_pdf

log = logging.getLogger(__name__)

GENERIC_ERROR = "Не удалось обработать документ, попробуйте ещё раз"
TEXT_CHANGED_ERROR = (
    "Обработка остановлена: оформление затронуло бы текст работы. Попробуйте режим «Проверить»."
)
TIMEOUT_MESSAGE = "Обработка заняла слишком много времени"
PDF_WARNING = "PDF-предпросмотр недоступен"

_engines: dict[str, Engine] = {}
_lock = threading.Lock()


def _sessionmaker(settings: Settings) -> sessionmaker[Session]:
    with _lock:
        engine = _engines.get(settings.database_url)
        if engine is None:
            engine = _engines[settings.database_url] = make_engine(settings.database_url)
    return make_sessionmaker(engine)


def _set_error(db: Session, job: Job, message: str) -> None:
    job.status = "error"
    job.error = message
    db.commit()


def mark_error_if_open(job_id: str, message: str | None = None) -> None:
    """Переводит задачу в error, если она ещё не завершена."""
    with _sessionmaker(get_settings())() as db:
        job = db.get(Job, job_id)
        if job is None or job.status in ("done", "error"):
            return
        _set_error(db, job, message or GENERIC_ERROR)


def _build_pdf(settings: Settings, directory: Path, docx_path: Path) -> str | None:
    """PDF необязателен: любая ошибка даёт None, DOCX не теряется."""
    try:
        return str(
            render_pdf(
                docx_path,
                directory,
                soffice=settings.soffice_path,
                timeout_s=settings.job_timeout_s,
            )
        )
    except Exception:  # includes JobTimeoutException: DOCX is saved, so it's just a PDF failure
        log.exception("PDF preview failed")
        return None


def run_job(job_id: str) -> None:
    settings = get_settings()
    with _sessionmaker(settings)() as db:
        job = db.get(Job, job_id)
        if job is None or job.status not in ("queued", "running"):
            return
        job.status = "running"
        db.commit()
        try:
            directory = storage.job_dir(settings, job_id)
            input_path = Path(job.input_path)
            data: bytes | str = (
                input_path.read_text(encoding="utf-8")
                if job.input_kind == "text"
                else input_path.read_bytes()
            )
            profile = Profile.model_validate(job.profile_snapshot)
            result = process(data, profile, job.mode)
            docx_path = directory / "result.docx"
            storage.write(docx_path, result.docx_bytes)
            report = dict(result.report)
            pdf = _build_pdf(settings, directory, docx_path)
            if pdf is None:
                report["warnings"] = [*report.get("warnings", []), PDF_WARNING]
            job.output_docx = str(docx_path)
            job.output_pdf = pdf
            job.report = report
            job.status = "done"
            db.commit()
        except JobTimeoutException:
            db.rollback()
            _set_error(db, job, TIMEOUT_MESSAGE)
        except InputError as exc:
            db.rollback()
            _set_error(db, job, str(exc))
        except TextChangedError:
            db.rollback()
            _set_error(db, job, TEXT_CHANGED_ERROR)
        except Exception:
            log.exception("Job %s failed", job_id)
            db.rollback()
            _set_error(db, job, GENERIC_ERROR)
