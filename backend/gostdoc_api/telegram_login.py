"""Проверка подписи данных виджета «Войти через Telegram»."""

from __future__ import annotations

import hashlib
import hmac

MAX_AGE = 86400
MAX_FUTURE = 300
MAX_TELEGRAM_ID = 2**63 - 1


class TelegramAuthError(Exception):
    """Подпись неверна, данные неполны или устарели."""


def verify(data: dict[str, str | int], bot_token: str, now: int) -> int:
    """Возвращает telegram_id или бросает TelegramAuthError."""
    given = data.get("hash")
    if not isinstance(given, str) or not given:
        raise TelegramAuthError("no hash")
    fields: dict[str, str] = {}
    for key, value in data.items():
        if key == "hash":
            continue
        if isinstance(value, bool) or not isinstance(value, str | int):
            raise TelegramAuthError("bad field type")
        fields[key] = str(value)
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(), given.lower().encode()):
        raise TelegramAuthError("bad signature")
    raw_id, raw_date = fields.get("id", ""), fields.get("auth_date", "")
    if not (raw_id.isascii() and raw_id.isdigit() and raw_date.isascii() and raw_date.isdigit()):
        raise TelegramAuthError("bad id or auth_date")
    tg_id = int(raw_id)
    if not 0 < tg_id <= MAX_TELEGRAM_ID or not -MAX_FUTURE <= now - int(raw_date) <= MAX_AGE:
        raise TelegramAuthError("bad id or stale")
    return tg_id
