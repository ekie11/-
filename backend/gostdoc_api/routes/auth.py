"""Регистрация, вход, выход."""

from __future__ import annotations

import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..auth import (
    COOKIE_NAME,
    DbDep,
    UserDep,
    create_session,
    destroy_session,
    hash_password,
    verify_dummy,
    verify_password,
)
from ..guest import claim_guest_jobs
from ..models import User
from ..telegram_login import TelegramAuthError, verify

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 320 or not _EMAIL_RE.match(v):
            raise ValueError("bad email")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("short password")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "telegram_name": user.telegram_name,
        "telegram_linked": user.telegram_id is not None,
    }


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: DbDep) -> dict:
    exists = HTTPException(status_code=409, detail="Этот email уже зарегистрирован")
    if db.scalars(select(User).where(User.email == body.email)).first():
        raise exists
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise exists from None
    settings = request.app.state.settings
    create_session(db, user, response, settings.cookie_secure)
    claim_guest_jobs(db, request, response, user, settings)
    return _user_out(user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DbDep) -> dict:
    email = body.email.strip().lower()
    user = db.scalars(select(User).where(User.email == email)).first() if email else None
    if user is None:
        verify_dummy(body.password)
        ok = False
    else:
        ok = verify_password(user.password_hash, body.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    settings = request.app.state.settings
    create_session(db, user, response, settings.cookie_secure)
    claim_guest_jobs(db, request, response, user, settings)
    return _user_out(user)


@router.post("/logout", status_code=204)
def logout(request: Request, db: DbDep) -> Response:
    destroy_session(db, request.cookies.get(COOKIE_NAME))
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return response


@router.get("/me")
def me(user: UserDep) -> dict:
    return _user_out(user)


def _verified_telegram_id(request: Request, body: dict[str, Any]) -> int:
    token = request.app.state.settings.telegram_bot_token
    if not token:
        raise HTTPException(status_code=503, detail="Функция не настроена")
    try:
        return verify(body, token, int(time.time()))
    except TelegramAuthError:
        raise HTTPException(
            status_code=401, detail="Не удалось подтвердить вход через Telegram"
        ) from None


def _telegram_name(body: dict[str, Any]) -> str | None:
    parts = [str(body.get("first_name") or ""), str(body.get("last_name") or "")]
    return " ".join(p.strip() for p in parts if p.strip())[:255] or None


@router.post("/telegram")
def telegram_login(body: dict[str, Any], request: Request, response: Response, db: DbDep) -> dict:
    tg_id = _verified_telegram_id(request, body)
    name = _telegram_name(body)
    user = db.scalars(select(User).where(User.telegram_id == tg_id)).first()
    if user is None:
        user = User(email=None, password_hash=None, telegram_id=tg_id, telegram_name=name)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:  # параллельный первый вход того же пользователя
            db.rollback()
            user = db.scalars(select(User).where(User.telegram_id == tg_id)).one()
    elif name and user.telegram_name != name:
        user.telegram_name = name
        db.commit()
    settings = request.app.state.settings
    create_session(db, user, response, settings.cookie_secure)
    claim_guest_jobs(db, request, response, user, settings)
    return _user_out(user)


@router.post("/telegram/link")
def telegram_link(body: dict[str, Any], request: Request, user: UserDep, db: DbDep) -> dict:
    tg_id = _verified_telegram_id(request, body)
    taken = HTTPException(status_code=409, detail="Этот Telegram уже привязан к другому аккаунту")
    if user.telegram_id is not None and user.telegram_id != tg_id:
        raise HTTPException(status_code=409, detail="К аккаунту уже привязан другой Telegram")
    other = db.scalars(select(User).where(User.telegram_id == tg_id)).first()
    if other is not None and other.id != user.id:
        raise taken
    user.telegram_id = tg_id
    user.telegram_name = _telegram_name(body) or user.telegram_name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise taken from None
    return _user_out(user)
