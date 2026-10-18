"""Описание полей профиля для редактора: группы, подписи правил, поля."""

from __future__ import annotations

import json
from functools import lru_cache

from gostdoc_engine.profile import FIELDS_FILE, PROFILES_DIR


@lru_cache
def load_fields() -> dict:
    return json.loads((PROFILES_DIR / FIELDS_FILE).read_text(encoding="utf-8"))


@lru_cache
def field_index() -> dict[tuple[str, str], dict]:
    return {(f["rule"], f["path"]): f for f in load_fields()["fields"]}
