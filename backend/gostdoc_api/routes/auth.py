"""Регистрация, вход, выход."""

from __future__ import annotations

import re

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
from ..models import User

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
    return {"id": user.id, "email": user.email}


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
    create_session(db, user, response, request.app.state.settings.cookie_secure)
    return _user_out(user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DbDep) -> dict:
    user = db.scalars(select(User).where(User.email == body.email.strip().lower())).first()
    if user is None:
        verify_dummy(body.password)
        ok = False
    else:
        ok = verify_password(user.password_hash, body.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    create_session(db, user, response, request.app.state.settings.cookie_secure)
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
