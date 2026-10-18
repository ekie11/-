"""Гостевой режим: первая задача без регистрации."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .auth import COOKIE_NAME, DbDep, _aware, _find_session, _token_hash
from .config import Settings
from .models import GuestSession, Job, User

GUEST_COOKIE = "guest"
GUEST_HOURS = 24
GUEST_JOB_LIMIT = 3
IP_JOB_LIMIT = 10
LIMIT_MESSAGE = "Зарегистрируйтесь, чтобы продолжить"


@dataclass
class Owner:
    user: User | None
    guest: GuestSession | None


def _find_guest(db: Session, token: str | None) -> GuestSession | None:
    if not token:
        return None
    row = db.scalars(
        select(GuestSession).where(GuestSession.token_hash == _token_hash(token))
    ).first()
    if row is None or _aware(row.expires_at) <= datetime.now(UTC):
        return None
    return row


def _set_guest_cookie(response: Response, token: str, secure: bool) -> None:
    response.set_cookie(
        GUEST_COOKIE,
        token,
        max_age=GUEST_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _owner(request: Request, db: Session, create: bool) -> Owner:
    row = _find_session(db, request.cookies.get(COOKIE_NAME))
    user = db.get(User, row.user_id) if row else None
    if user is not None:
        return Owner(user, None)
    guest = _find_guest(db, request.cookies.get(GUEST_COOKIE))
    if guest is not None:
        return Owner(None, guest)
    if not create:
        raise HTTPException(status_code=401, detail="Нужно войти")
    return Owner(None, None)


def mint_guest(db: Session, request: Request, response: Response) -> GuestSession:
    """Создаёт гостя и ставит cookie; вызывать только после всех проверок запроса."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    guest = GuestSession(
        token_hash=_token_hash(token),
        created_at=now,
        expires_at=now + timedelta(hours=GUEST_HOURS),
    )
    db.add(guest)
    db.commit()
    _set_guest_cookie(response, token, request.app.state.settings.cookie_secure)
    return guest


def owner_or_guest(request: Request, db: DbDep) -> Owner:
    """Для чтения: пользователь или существующий гость, иначе 401."""
    return _owner(request, db, create=False)


def owner_or_new_guest(request: Request, db: DbDep) -> Owner:
    """Для POST /jobs: без владельца возвращает Owner(None, None), гость создаётся позже."""
    return _owner(request, db, create=True)


OwnerDep = Annotated[Owner, Depends(owner_or_guest)]
NewOwnerDep = Annotated[Owner, Depends(owner_or_new_guest)]


def check_guest_limits(db: Session, guest: GuestSession | None, ip: str, now: datetime) -> None:
    # Подсчёт и последующая вставка задачи не атомарны: при гонке возможны
    # несколько лишних задач сверх лимита, это допустимо.
    since = now - timedelta(hours=24)
    if guest is not None:
        per_guest = db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.guest_id == guest.id, Job.created_at > since)
        )
        if per_guest >= GUEST_JOB_LIMIT:
            raise HTTPException(status_code=429, detail=LIMIT_MESSAGE)
    per_ip = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.client_ip == ip, Job.user_id.is_(None), Job.created_at > since)
    )
    if per_ip >= IP_JOB_LIMIT:
        raise HTTPException(status_code=429, detail=LIMIT_MESSAGE)


def claim_guest_jobs(
    db: Session, request: Request, response: Response, user: User, settings: Settings
) -> int:
    """Переносит задачи гостя (по cookie) в аккаунт; стирает гостевую сессию и cookie."""
    guest = _find_guest(db, request.cookies.get(GUEST_COOKIE))
    if guest is None:
        return 0
    now = datetime.now(UTC)
    result = db.execute(
        update(Job)
        .where(
            Job.guest_id == guest.id,
            Job.status != "expired",
            (Job.expires_at.is_(None)) | (Job.expires_at > now),
        )
        .values(
            user_id=user.id,
            guest_id=None,
            expires_at=now + timedelta(days=settings.file_ttl_days),
        )
    )
    db.delete(guest)
    db.commit()
    response.delete_cookie(GUEST_COOKIE, path="/", httponly=True, samesite="lax")
    return result.rowcount
