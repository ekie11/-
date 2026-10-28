"""Публичные настройки для фронтенда."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["config"])


@router.get("/config")
def get_config(request: Request) -> dict:
    s = request.app.state.settings
    name = s.telegram_bot_username.strip().lstrip("@")
    enabled = bool(s.telegram_bot_token and name)
    return {"telegram_bot_username": name if enabled else None}
