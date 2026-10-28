"""Пароли и сессии."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .bot_auth import bot_user
from .db import get_db
from .models import SessionToken, User

COOKIE_NAME = "session"
SESSION_DAYS = 30

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(p: str) -> str:
    return _hasher.hash(p)


def verify_password(h: str | None, p: str) -> bool:
    if not h:
        return False
    try:
        return _hasher.verify(h, p)
    except (VerificationError, InvalidHashError):
        return False


def verify_dummy(p: str) -> None:
    """Выравнивает время ответа для неизвестного email."""
    verify_password(_DUMMY_HASH, p)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, response: Response, secure: bool) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
    db.add(SessionToken(user_id=user.id, token_hash=_token_hash(token), expires_at=expires))
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _find_session(db: Session, token: str | None) -> SessionToken | None:
    if not token:
        return None
    row = db.scalars(
        select(SessionToken).where(SessionToken.token_hash == _token_hash(token))
    ).first()
    if row is None or _aware(row.expires_at) <= datetime.now(UTC):
        return None
    return row


DbDep = Annotated[Session, Depends(get_db)]


def current_user(request: Request, db: DbDep) -> User:
    bot = bot_user(request, db)
    if bot is not None:
        return bot
    row = _find_session(db, request.cookies.get(COOKIE_NAME))
    user = db.get(User, row.user_id) if row else None
    if user is None:
        raise HTTPException(status_code=401, detail="Нужно войти")
    return user


def destroy_session(db: Session, token: str | None) -> None:
    if not token:
        return
    for row in db.scalars(
        select(SessionToken).where(SessionToken.token_hash == _token_hash(token))
    ):
        db.delete(row)
    db.commit()


UserDep = Annotated[User, Depends(current_user)]
