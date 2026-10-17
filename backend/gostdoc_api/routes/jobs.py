"""Задачи обработки: загрузка, статус, результаты."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from rq import Callback, Queue
from sqlalchemy import select

from gostdoc_engine.importer import MAX_BYTES, InputError, load_docx, text_to_docx

from .. import storage
from ..auth import DbDep, UserDep
from ..models import Job
from ..profiles_service import resolve_profile
from ..queue import get_queue, on_job_failure
from ..worker import run_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
NEED_INPUT = "Загрузите файл или вставьте текст"
NOT_FOUND = "Задача не найдена"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def _read_limited(file: UploadFile) -> bytes:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise InputError("Файл больше 20 МБ")
    return data


@router.post("", status_code=202)
async def create_job(
    request: Request,
    db: DbDep,
    user: UserDep,
    queue: Annotated[Queue, Depends(get_queue)],
    profile_id: Annotated[str, Form()],
    mode: Annotated[Literal["check", "format"], Form()],
    file: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
) -> dict:
    settings = request.app.state.settings
    has_file = file is not None and bool(file.filename)
    if has_file == (text is not None):
        raise HTTPException(400, NEED_INPUT)
    try:
        if has_file:
            payload: bytes = await _read_limited(file)
            load_docx(payload)
            name, content = "input.docx", payload
        else:
            text_to_docx(text)
            name, content = "input.txt", text.encode("utf-8")
    except InputError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        profile = resolve_profile(db, user, profile_id)
    except LookupError as exc:
        raise HTTPException(404, "Профиль не найден") from exc

    job_id = str(uuid.uuid4())
    input_path = storage.job_dir(settings, job_id) / name
    storage.write(input_path, content)
    now = datetime.now(UTC)
    job = Job(
        id=job_id,
        user_id=user.id,
        profile_id=profile_id,
        profile_snapshot=profile.model_dump(),
        mode=mode,
        input_kind="docx" if has_file else "text",
        status="queued",
        input_path=str(input_path),
        created_at=now,
        expires_at=now + timedelta(days=settings.file_ttl_days),
    )
    db.add(job)
    db.commit()
    try:
        queue.enqueue(
            run_job,
            job_id,
            job_id=job_id,
            job_timeout=settings.job_timeout_s,
            on_failure=Callback(on_job_failure),
        )
    except Exception as exc:
        storage.delete_job_files(settings, job_id)
        job.status = "error"
        job.error = "Сервис обработки временно недоступен, попробуйте позже"
        db.commit()
        raise HTTPException(503, job.error) from exc
    return {"id": job.id, "status": job.status}


def _own(db, user, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, NOT_FOUND)
    return job


@router.get("")
def list_jobs(db: DbDep, user: UserDep) -> list[dict]:
    jobs = db.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()))
    return [
        {
            "id": j.id,
            "status": j.status,
            "mode": j.mode,
            "profile_name": (j.profile_snapshot or {}).get("name"),
            "created_at": _iso(j.created_at),
            "expires_at": _iso(j.expires_at),
        }
        for j in jobs
    ]


@router.get("/{job_id}")
def get_job(job_id: str, db: DbDep, user: UserDep) -> dict:
    j = _own(db, user, job_id)
    return {
        "id": j.id,
        "status": j.status,
        "mode": j.mode,
        "error": j.error,
        "report": j.report,
        "has_pdf": j.output_pdf is not None,
        "created_at": _iso(j.created_at),
        "expires_at": _iso(j.expires_at),
    }


def _file(db, user, job_id: str, kind: str) -> FileResponse:
    j = _own(db, user, job_id)
    if j.status == "expired":
        raise HTTPException(410, "Срок хранения файла истёк")
    if j.status != "done":
        raise HTTPException(409, "Результат ещё не готов")
    if kind == "docx":
        path, media = j.output_docx, DOCX_TYPE
    else:
        path, media = j.output_pdf, "application/pdf"
        if path is None:
            raise HTTPException(404, "PDF-предпросмотр недоступен")
    if not path or not Path(path).is_file():
        raise HTTPException(404, "Файл результата не найден")
    return FileResponse(path, media_type=media, filename=f"result.{kind}")


@router.get("/{job_id}/docx")
def download_docx(job_id: str, db: DbDep, user: UserDep) -> FileResponse:
    return _file(db, user, job_id, "docx")


@router.get("/{job_id}/pdf")
def download_pdf(job_id: str, db: DbDep, user: UserDep) -> FileResponse:
    return _file(db, user, job_id, "pdf")
