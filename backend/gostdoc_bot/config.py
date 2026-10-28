"""Настройки бота из окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    token: str
    api_secret: str
    api_url: str
    redis_url: str
    site_url: str


def load_config() -> Config:
    env = os.environ
    return Config(
        token=env.get("TELEGRAM_BOT_TOKEN", "").strip(),
        api_secret=env.get("BOT_API_SECRET", "").strip(),
        api_url=env.get("API_URL", "http://api:8000").strip(),
        redis_url=env.get("REDIS_URL", "redis://localhost:6379/0").strip(),
        site_url=env.get("SITE_URL", "").strip().rstrip("/"),
    )
