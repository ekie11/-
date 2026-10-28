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
    trusted_proxies: tuple[str, ...] = ()
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model: str = "glm-4.5-flash"
    llm_timeout_s: int = 120
    extract_user_daily: int = 5
    extract_global_daily: int = 500
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    bot_api_secret: str = ""
    site_url: str = ""


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
        llm_api_key=env.get("LLM_API_KEY", "").strip(),
        llm_base_url=env.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").strip(),
        llm_model=env.get("LLM_MODEL", "glm-4.5-flash").strip(),
        llm_timeout_s=int(env.get("LLM_TIMEOUT_S", "120")),
        extract_user_daily=int(env.get("EXTRACT_USER_DAILY", "5")),
        extract_global_daily=int(env.get("EXTRACT_GLOBAL_DAILY", "500")),
        telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_bot_username=env.get("TELEGRAM_BOT_USERNAME", "").strip(),
        bot_api_secret=env.get("BOT_API_SECRET", "").strip(),
        site_url=env.get("SITE_URL", "").strip(),
        trusted_proxies=tuple(
            p.strip() for p in env.get("TRUSTED_PROXIES", "").split(",") if p.strip()
        ),
    )
