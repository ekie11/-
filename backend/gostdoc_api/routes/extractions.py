"""Извлечение требований из методички: загрузка, статус, сборка профиля."""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, ValidationError, field_validator
from rq import Callback, Queue
from sqlalchemy import func, select

from gostdoc_engine.importer import MAX_BYTES
from gostdoc_engine.profile import Profile

from .. import profiles_service as svc
from ..auth import DbDep, current_user
from ..guideline_text import GuidelineError, check_text, extract_text
from ..llm import extraction_timeout_s
from ..models import Extraction, User
from ..queue import get_extraction_queue, on_extraction_failure
from ..worker import run_extraction_job

router = APIRouter(prefix="/extractions", tags=["extractions"])

DEFAULT_BASE = "gost-7.32-2017"
NEED_INPUT = "Загрузите файл или вставьте текст"
NOT_FOUND = "Извлечение не найдено"
NOT_CONFIGURED = "Функция не настроена"
BASE_NOT_FOUND = "Базовый профиль не найден"
USER_LIMIT = "Лимит извлечений на сегодня исчерпан"
GLOBAL_LIMIT = "Сервис перегружен, попробуйте завтра"
QUEUE_DOWN = "Сервис обработки временно недоступен, попробуйте позже"
FAILURE_TTL_S = 60

UserDep = Annotated[User, Depends(current_user)]


class ProfileFromExtraction(BaseModel):
    accepted: list[int]
    name: str = Field(max_length=255)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Укажите название профиля")
        return v


async def _read_limited(file: UploadFile) -> bytes:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise GuidelineError("Файл больше 20 МБ", 413)
    return data


def _used(db, since: datetime, user: User | None = None) -> int:
    q = select(func.count(Extraction.id)).where(
        Extraction.created_at >= since, Extraction.counts_toward_limit.is_(True)
    )
    if user is not None:
        q = q.where(Extraction.user_id == user.id)
    return db.scalar(q) or 0


def _since() -> datetime:
    return datetime.now(UTC) - timedelta(hours=24)


@router.post("", status_code=202)
async def create_extraction(
    request: Request,
    db: DbDep,
    user: UserDep,
    queue: Annotated[Queue, Depends(get_extraction_queue)],
    base_profile_id: Annotated[str, Form()] = DEFAULT_BASE,
    file: Annotated[UploadFile | None, File()] = None,
    text: Annotated[str | None, Form()] = None,
) -> dict:
    settings = request.app.state.settings
    if not settings.llm_api_key:
        raise HTTPException(503, NOT_CONFIGURED)
    if svc.builtin_by_id(base_profile_id) is None:
        raise HTTPException(400, BASE_NOT_FOUND)
    has_file = file is not None and bool(file.filename)
    if has_file == (text is not None):
        raise HTTPException(400, NEED_INPUT)
    try:
        if has_file:
            source = (file.filename or "")[:255]
            guideline = check_text(extract_text(await _read_limited(file), source))
        else:
            source = None
            guideline = check_text(text)
    except GuidelineError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    since = _since()
    if _used(db, since, user) >= settings.extract_user_daily:
        raise HTTPException(429, USER_LIMIT)
    if _used(db, since) >= settings.extract_global_daily:
        raise HTTPException(429, GLOBAL_LIMIT)

    row = Extraction(
        id=uuid.uuid4().hex,
        user_id=user.id,
        status="queued",
        base_profile_id=base_profile_id,
        source_name=source,
        counts_toward_limit=True,
    )
    db.add(row)
    db.commit()
    timeout = extraction_timeout_s(settings)
    try:
        queue.enqueue(
            run_extraction_job,
            row.id,
            guideline,
            job_id=row.id,
            job_timeout=timeout,
            ttl=timeout,  # ttl только ограничивает хранение результата в RQ; зависшую в очереди задачу чистит cleanup (текст остаётся в Redis до её запуска)
            result_ttl=0,  # текст методички не держим в Redis после выполнения
            failure_ttl=FAILURE_TTL_S,
            on_failure=Callback(on_extraction_failure),
        )
    except Exception as exc:
        row.status = "failed"
        row.error = QUEUE_DOWN
        row.counts_toward_limit = False
        db.commit()
        raise HTTPException(503, QUEUE_DOWN) from exc
    return {"id": row.id}


@router.get("/quota")
def quota(request: Request, db: DbDep, user: UserDep) -> dict:
    limit = request.app.state.settings.extract_user_daily
    return {"used": _used(db, _since(), user), "limit": limit}


def _own(db, user: User, extraction_id: str) -> Extraction:
    row = db.get(Extraction, extraction_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, NOT_FOUND)
    return row


@router.get("/{extraction_id}")
def get_extraction(extraction_id: str, db: DbDep, user: UserDep) -> dict:
    row = _own(db, user, extraction_id)
    return {
        "id": row.id,
        "status": row.status,
        "base_profile_id": row.base_profile_id,
        "source_name": row.source_name,
        "result": row.result,
        "error": row.error,
    }


@router.post("/{extraction_id}/profile", status_code=201)
def create_profile(
    extraction_id: str, body: ProfileFromExtraction, db: DbDep, user: UserDep
) -> dict:
    row = _own(db, user, extraction_id)
    if row.status != "done":
        raise HTTPException(409, "Результат ещё не готов")
    base = svc.builtin_by_id(row.base_profile_id)
    if base is None:
        raise HTTPException(400, BASE_NOT_FOUND)
    found = (row.result or {}).get("found", [])
    if any(not 0 <= i < len(found) for i in body.accepted):
        raise HTTPException(400, "Некорректный номер требования")
    data = copy.deepcopy(base.model_dump())
    data.update(id="", name=body.name, base=base.id, readonly=False)
    try:
        for i in dict.fromkeys(body.accepted):
            item = found[i]
            rule = data["rules"][item["rule"]]
            rule["value"][item["path"]] = item["value"]
            rule["enabled"] = True
        profile = Profile.model_validate(data)
    except (KeyError, TypeError, ValidationError) as exc:
        detail = (
            "; ".join(str(e["msg"]).removeprefix("Value error, ") for e in exc.errors())
            if isinstance(exc, ValidationError)
            else "требование не подходит к профилю"
        )
        raise HTTPException(400, f"Некорректный профиль: {detail}") from None
    return {"profile_id": svc.save_new(db, user, profile).id}
