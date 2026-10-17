"""Профили: поиск, создание, изменение."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from gostdoc_engine.profile import Profile, list_builtin_profiles

from .models import ProfileRow, User


def builtin_by_id(profile_id: str) -> Profile | None:
    for p in list_builtin_profiles():
        if p.id == profile_id:
            return p
    return None


def get_row(db: Session, user: User, profile_id: str) -> ProfileRow | None:
    row = db.get(ProfileRow, profile_id)
    if row is None or row.user_id != user.id:
        return None
    return row


def resolve_profile(db: Session, user: User, profile_id: str) -> Profile:
    builtin = builtin_by_id(profile_id)
    if builtin is not None:
        return builtin
    row = get_row(db, user, profile_id)
    if row is None:
        raise LookupError(profile_id)
    return Profile.model_validate(row.data)


def save_new(db: Session, user: User, profile: Profile) -> Profile:
    profile = profile.model_copy(update={"id": str(uuid.uuid4()), "readonly": False})
    db.add(
        ProfileRow(
            id=profile.id,
            user_id=user.id,
            name=profile.name,
            base_id=profile.base,
            data=profile.model_dump(),
        )
    )
    db.commit()
    return profile


def update_row(db: Session, row: ProfileRow, profile: Profile) -> Profile:
    profile = profile.model_copy(update={"id": row.id, "readonly": False})
    row.name = profile.name
    row.data = profile.model_dump()
    db.commit()
    return profile


def list_own(db: Session, user: User) -> list[Profile]:
    rows = db.scalars(
        select(ProfileRow)
        .where(ProfileRow.user_id == user.id)
        .order_by(ProfileRow.updated_at.desc())
    )
    return [Profile.model_validate(r.data) for r in rows]


def diff_from_base(profile: Profile) -> dict[str, bool]:
    base = builtin_by_id(profile.base) if profile.base else None
    out: dict[str, bool] = {}
    for key, rule in profile.rules.items():
        if base is None or profile.readonly:
            out[key] = False
        else:
            b = base.rules.get(key)
            out[key] = b is None or rule.model_dump() != b.model_dump()
    return out
