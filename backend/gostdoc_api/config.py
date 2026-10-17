"""Настройки приложения: только из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    storage_dir: str
    cookie_secure: bool = True
    soffice_path: str = "soffice"
    job_timeout_s: int = 120
    file_ttl_days: int = 30


@lru_cache
def get_settings() -> Settings:
    env = os.environ
    return Settings(
        database_url=env.get("DATABASE_URL", "sqlite:///./gostdoc.db"),
        redis_url=env.get("REDIS_URL", "redis://localhost:6379/0"),
        storage_dir=env.get("STORAGE_DIR", "./storage"),
        cookie_secure=_bool(env.get("COOKIE_SECURE"), True),
        soffice_path=env.get("SOFFICE_PATH", "soffice"),
        job_timeout_s=int(env.get("JOB_TIMEOUT_S", "120")),
        file_ttl_days=int(env.get("FILE_TTL_DAYS", "30")),
    )
