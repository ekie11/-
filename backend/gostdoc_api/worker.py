"""Воркер: выполняет задачу обработки по снимку профиля."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from docx import Document
from rq.timeouts import JobTimeoutException
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from gostdoc_engine.importer import InputError
from gostdoc_engine.pipeline import process
from gostdoc_engine.profile import Profile
from gostdoc_engine.textguard import TextChangedError
from gostdoc_engine.toc import has_toc_field, set_page_numbers, set_update_fields

from . import storage
from .config import Settings, get_settings
from .db import make_engine, make_sessionmaker
from .extraction import run_extraction
from .llm import LlmError
from .lo_pages import page_numbers_and_pdf
from .models import Extraction, Job
from .pdf import render_pdf

log = logging.getLogger(__name__)

GENERIC_ERROR = "Не удалось обработать документ, попробуйте ещё раз"
TEXT_CHANGED_ERROR = (
    "Обработка остановлена: оформление затронуло бы текст работы. Попробуйте режим «Проверить»."
)
TIMEOUT_MESSAGE = "Обработка заняла слишком много времени"
PDF_WARNING = "PDF-предпросмотр недоступен"
TOC_WARNING = "Номера страниц в оглавлении обновятся при открытии в Word"

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


def _pdf_timeout(settings: Settings) -> int:
    return max(10, min(60, settings.job_timeout_s // 3))


def _toc_pages_and_pdf(settings: Settings, docx_path: Path) -> tuple[str | None, str | None]:
    """Вписывает номера страниц в оглавление и строит PDF; возвращает (pdf, предупреждение).

    Только если в DOCX есть поле TOC. Ошибка LibreOffice → updateFields и предупреждение,
    PDF в этом случае строит вызывающий обычным способом.
    """
    try:
        doc = Document(str(docx_path))
        if not has_toc_field(doc):
            return None, None
    except Exception:
        log.exception("TOC check failed")
        return None, None
    out_pdf = docx_path.with_suffix(".pdf")
    timed_out: JobTimeoutException | None = None
    try:
        pages = page_numbers_and_pdf(
            docx_path, out_pdf, soffice=settings.soffice_path, timeout_s=_pdf_timeout(settings)
        )
        links = len(doc.element.body.xpath(".//w:hyperlink[@w:anchor]"))
        if set_page_numbers(doc, pages) < links:
            raise ValueError("номера страниц получены не для всех пунктов оглавления")
        _save_atomic(doc, docx_path)
        return str(out_pdf), None
    except JobTimeoutException as exc:
        timed_out = exc
    except Exception:
        log.exception("TOC page numbers failed")
    out_pdf.unlink(missing_ok=True)
    try:
        doc = Document(str(docx_path))
        set_update_fields(doc)
        _save_atomic(doc, docx_path)
    except Exception:
        log.exception("set_update_fields failed")
    if timed_out is not None:
        raise timed_out
    return None, TOC_WARNING


def _save_atomic(doc, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    doc.save(str(tmp))
    os.replace(tmp, path)


def _build_pdf(settings: Settings, directory: Path, docx_path: Path) -> str | None:
    """PDF необязателен: любая ошибка даёт None, DOCX не теряется."""
    try:
        return str(
            render_pdf(
                docx_path,
                directory,
                soffice=settings.soffice_path,
                timeout_s=_pdf_timeout(settings),
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
            pdf = None
            skip_pdf = False
            if job.mode == "format":
                try:
                    pdf, toc_warning = _toc_pages_and_pdf(settings, docx_path)
                except JobTimeoutException:
                    # DOCX сохранён (с updateFields); как и при таймауте PDF — без предпросмотра
                    log.exception("TOC phase timed out")
                    pdf, toc_warning, skip_pdf = None, TOC_WARNING, True
                if toc_warning:
                    report["warnings"] = [*report.get("warnings", []), toc_warning]
            if pdf is None and not skip_pdf:
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


LLM_UNAVAILABLE = "Сервис распознавания временно недоступен, попробуйте позже"
EXTRACTION_ERROR = "Не удалось обработать методичку"


def _fail_extraction(db: Session, row: Extraction, message: str, counts: bool) -> None:
    row.status = "failed"
    row.error = message
    row.counts_toward_limit = counts
    db.commit()


def mark_extraction_failed_if_open(extraction_id: str, message: str | None = None) -> None:
    """Переводит извлечение в failed, если оно ещё не завершено."""
    with _sessionmaker(get_settings())() as db:
        row = db.get(Extraction, extraction_id)
        if row is None or row.status in ("done", "failed"):
            return
        _fail_extraction(db, row, message or EXTRACTION_ERROR, True)


def run_extraction_job(extraction_id: str, text: str) -> None:
    settings = get_settings()
    with _sessionmaker(settings)() as db:
        row = db.get(Extraction, extraction_id)
        if row is None or row.status not in ("queued", "running"):
            return
        row.status = "running"
        db.commit()
        try:
            result = run_extraction(text, settings)
            row.result = result
            row.status = "done"
            db.commit()
        except LlmError:
            db.rollback()
            _fail_extraction(db, row, LLM_UNAVAILABLE, False)
        except Exception as exc:  # noqa: BLE001
            # текст методички не попадает в лог: только тип исключения
            log.error("Extraction %s failed: %s", extraction_id, type(exc).__name__)
            db.rollback()
            _fail_extraction(db, row, EXTRACTION_ERROR, True)
