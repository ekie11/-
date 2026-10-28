"""Вход бота: заголовки X-Bot-Secret и X-Telegram-User вместо cookie сессии."""

from __future__ import annotations

import hmac
from urllib.parse import unquote

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import User

SECRET_HEADER = "X-Bot-Secret"
USER_HEADER = "X-Telegram-User"
NAME_HEADER = "X-Telegram-Name"


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Нужно войти")


def bot_user(request: Request, db: Session) -> User | None:
    """None — запрос не от бота; 401 — заголовок есть, но он неверен; иначе пользователь."""
    given = request.headers.get(SECRET_HEADER)
    if given is None:
        return None
    expected = request.app.state.settings.bot_api_secret
    if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
        raise _unauthorized()
    raw = request.headers.get(USER_HEADER, "").strip()
    if not (raw.isascii() and raw.isdigit()) or len(raw) > 19 or not 0 < int(raw) < 2**63:
        raise _unauthorized()
    tg_id = int(raw)
    # HTTP-заголовки только latin-1, поэтому бот передаёт имя в процент-кодировке
    name = unquote(request.headers.get(NAME_HEADER) or "").strip()[:255] or None

    user = db.scalars(select(User).where(User.telegram_id == tg_id)).first()
    if user is None:
        user = User(email=None, password_hash=None, telegram_id=tg_id, telegram_name=name)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:  # параллельный первый запрос того же пользователя
            db.rollback()
            user = db.scalars(select(User).where(User.telegram_id == tg_id)).one()
    elif name and user.telegram_name != name:
        user.telegram_name = name
        db.commit()
    return user
