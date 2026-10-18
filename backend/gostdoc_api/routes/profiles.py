"""Профили требований."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field, ValidationError

from gostdoc_engine.profile import Profile

from .. import fields as fields_mod
from .. import profiles_service as svc
from ..auth import COOKIE_NAME, DbDep, UserDep, _find_session
from ..models import User

router = APIRouter(prefix="/profiles", tags=["profiles"])
fields_router = APIRouter(tags=["profiles"])

FORBIDDEN = "Готовый ГОСТ-профиль нельзя изменить — создайте свой на его основе"
NOT_FOUND = "Профиль не найден"
MAX_IMPORT_BYTES = 1024 * 1024


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_id: str | None = None
    rules: dict | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    rules: dict | None = None


def _bad(exc: ValidationError) -> HTTPException:
    msgs = "; ".join(str(e["msg"]).removeprefix("Value error, ") for e in exc.errors())
    return HTTPException(400, f"Некорректный профиль: {msgs}")


def _full(profile: Profile) -> dict:
    return {**profile.model_dump(), "diff": svc.diff_from_base(profile)}


def _summary(p: Profile) -> dict:
    return {"id": p.id, "name": p.name, "base": p.base, "readonly": p.readonly}


def _own_row(db, user, profile_id):
    row = svc.get_row(db, user, profile_id)
    if row is None:
        raise HTTPException(404, NOT_FOUND)
    return row


def _optional_user(request: Request, db: DbDep) -> User | None:
    """Пользователь по сессии или None (гость/аноним); гостя не создаёт."""
    row = _find_session(db, request.cookies.get(COOKIE_NAME))
    return db.get(User, row.user_id) if row else None


OptionalUserDep = Annotated[User | None, Depends(_optional_user)]


@router.get("")
def list_profiles(db: DbDep, user: OptionalUserDep) -> list[dict]:
    from gostdoc_engine.profile import list_builtin_profiles

    own = svc.list_own(db, user) if user is not None else []
    return [_summary(p) for p in list_builtin_profiles() + own]


@router.post("", status_code=201)
def create_profile(body: ProfileCreate, db: DbDep, user: UserDep) -> dict:
    try:
        if body.base_id is not None:
            base = svc.builtin_by_id(body.base_id)
            if base is None:
                raise HTTPException(404, NOT_FOUND)
            data = base.model_dump()
            data.update(name=body.name, base=base.id)
            if body.rules is not None:
                data["rules"] = body.rules
        elif body.rules is not None:
            data = {
                "id": "",
                "name": body.name,
                "base": None,
                "readonly": False,
                "rules": body.rules,
            }
        else:
            raise HTTPException(400, "Укажите базовый профиль или правила")
        profile = Profile.model_validate(data)
    except ValidationError as exc:
        raise _bad(exc) from None
    return _full(svc.save_new(db, user, profile))


@router.post("/import", status_code=201)
async def import_profile(db: DbDep, user: UserDep, file: Annotated[UploadFile, File()]) -> dict:
    try:
        data = await file.read(MAX_IMPORT_BYTES + 1)
        if len(data) > MAX_IMPORT_BYTES:
            raise HTTPException(400, "Файл профиля слишком большой")
        raw = json.loads(data.decode("utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("ожидался объект JSON")
        raw.update(id="", readonly=False)
        if not (isinstance(raw.get("base"), str) and svc.builtin_by_id(raw["base"])):
            raw["base"] = None
        profile = Profile.model_validate(raw)
        if not 1 <= len(profile.name) <= 200:
            raise ValueError("недопустимое имя профиля")
    except (ValueError, TypeError, RecursionError, ValidationError) as exc:
        # json.JSONDecodeError и UnicodeDecodeError — подклассы ValueError
        if isinstance(exc, ValidationError):
            detail = "; ".join(str(e["msg"]).removeprefix("Value error, ") for e in exc.errors())
        else:
            detail = str(exc)
        raise HTTPException(400, f"Файл профиля повреждён: {detail}") from None
    return _full(svc.save_new(db, user, profile))


@router.get("/{profile_id}")
def get_profile(profile_id: str, db: DbDep, user: OptionalUserDep) -> dict:
    try:
        return _full(svc.resolve_profile(db, user, profile_id))
    except LookupError:
        raise HTTPException(404, NOT_FOUND) from None


@router.put("/{profile_id}")
def update_profile(profile_id: str, body: ProfileUpdate, db: DbDep, user: UserDep) -> dict:
    if svc.builtin_by_id(profile_id):
        raise HTTPException(403, FORBIDDEN)
    row = _own_row(db, user, profile_id)
    data = dict(row.data)
    if body.name is not None:
        data["name"] = body.name
    if body.rules is not None:
        data["rules"] = body.rules
    try:
        profile = Profile.model_validate(data)
    except ValidationError as exc:
        raise _bad(exc) from None
    return _full(svc.update_row(db, row, profile))


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: str, db: DbDep, user: UserDep) -> Response:
    if svc.builtin_by_id(profile_id):
        raise HTTPException(403, FORBIDDEN)
    db.delete(_own_row(db, user, profile_id))
    db.commit()
    return Response(status_code=204)


@router.get("/{profile_id}/export")
def export_profile(profile_id: str, db: DbDep, user: UserDep) -> Response:
    try:
        profile = svc.resolve_profile(db, user, profile_id)
    except LookupError:
        raise HTTPException(404, NOT_FOUND) from None
    return Response(
        content=json.dumps(profile.model_dump(), ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{profile.id}.json"'},
    )


@fields_router.get("/profile-fields")
def profile_fields(request: Request) -> dict:
    enabled = bool(request.app.state.settings.llm_api_key)
    return {**fields_mod.load_fields(), "extraction_enabled": enabled}
