"""Модель профиля требований."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator

KNOWN_RULE_KEYS: frozenset[str] = frozenset(
    {
        "page.size",
        "page.margins",
        "body.font_name",
        "body.font_size",
        "body.line_spacing",
        "body.first_line_indent",
        "body.alignment",
        "headings.section",
        "headings.structural",
        "captions.figure",
        "captions.table",
        "page_numbers",
        "bibliography",
        "toc",
    }
)

DEFAULT_PROFILE_ID = "gost-7.32-2017"
PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
# Не профиль, а описание полей редактора (отдаёт API).
FIELDS_FILE = "fields.json"


class RuleConfig(BaseModel):
    value: dict
    severity: Literal["error", "recommendation"]
    enabled: bool = True
    source: str


class Profile(BaseModel):
    id: str
    name: str
    base: str | None
    readonly: bool
    rules: dict[str, RuleConfig]

    @field_validator("rules")
    @classmethod
    def _known_keys(cls, rules: dict[str, RuleConfig]) -> dict[str, RuleConfig]:
        unknown = sorted(set(rules) - KNOWN_RULE_KEYS)
        if unknown:
            raise ValueError(f"Неизвестные ключи правил: {', '.join(unknown)}")
        return rules


def load_profile(path: Path) -> Profile:
    return Profile.model_validate_json(Path(path).read_text(encoding="utf-8"))


def builtin_profile(profile_id: str) -> Profile:
    if not re.fullmatch(r"[a-z0-9.\-]+", profile_id):
        raise ValueError(f"Недопустимый идентификатор профиля: {profile_id!r}")
    filename = profile_id.replace("-", "_").replace(".", "_") + ".json"
    path = PROFILES_DIR / filename
    if filename == FIELDS_FILE or not path.is_file():
        raise ValueError(f"Неизвестный профиль: {profile_id}")
    return load_profile(path)


def list_builtin_profiles() -> list[Profile]:
    profiles = [load_profile(p) for p in sorted(PROFILES_DIR.glob("*.json")) if p.name != FIELDS_FILE]
    # ГОСТ 7.32-2017 — профиль по умолчанию, всегда первый
    return sorted(profiles, key=lambda p: p.id != DEFAULT_PROFILE_ID)
