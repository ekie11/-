"""Клиент OpenAI-совместимой модели: один запрос, ответ — JSON-объект."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable

import httpx

from .config import Settings

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class LlmError(Exception):
    """Модель недоступна или вернула непригодный ответ."""


# При 429 (лимит параллельных запросов провайдера) ждём и повторяем до трёх раз.
RATE_BACKOFF_S = (5, 15, 30)
RATE_WAIT_CAP_S = 30
OTHER_RETRIES = 1
MAX_REQUESTS = 1 + len(RATE_BACKOFF_S) + OTHER_RETRIES  # худший случай: все виды повторов


def extraction_timeout_s(settings: Settings) -> int:
    """Лимит времени задачи извлечения: все запросы по таймауту плюс все паузы и запас."""
    worst = settings.llm_timeout_s * MAX_REQUESTS + sum(RATE_BACKOFF_S) + 30
    return max(300, int(worst))


class _Retry(Exception):
    def __init__(self, reason: str = "", wait: float | None = None, rate_limited: bool = False):
        super().__init__(reason)
        self.wait = wait
        self.rate_limited = rate_limited


def _retry_after(resp: httpx.Response) -> float | None:
    try:
        value = float(resp.headers.get("Retry-After", ""))
    except ValueError:
        return None
    return value if value >= 0 else None


def _parse(content: str) -> dict:
    text = content.strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise _Retry("invalid json") from exc
    if not isinstance(data, dict):
        raise _Retry("not an object")
    return data


def _once(client: httpx.Client, url: str, headers: dict, body: dict) -> dict:
    try:
        resp = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise _Retry(type(exc).__name__) from exc
    if resp.status_code == 429:
        raise _Retry("status 429", wait=_retry_after(resp), rate_limited=True)
    if resp.status_code >= 500:
        raise _Retry(f"status {resp.status_code}")
    if resp.status_code >= 400:
        raise LlmError(f"Модель отклонила запрос: HTTP {resp.status_code}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise _Retry("bad response shape") from exc
    if not isinstance(content, str):
        raise _Retry("bad content")
    return _parse(content)


def chat_json(
    system: str,
    user: str,
    *,
    settings: Settings,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }
    last = ""
    rate_used = other_used = 0
    with httpx.Client(timeout=settings.llm_timeout_s, transport=transport) as client:
        while True:
            try:
                return _once(client, url, headers, body)
            except _Retry as exc:
                last = str(exc)
                if exc.rate_limited and rate_used < len(RATE_BACKOFF_S):
                    wait = RATE_BACKOFF_S[rate_used] if exc.wait is None else exc.wait
                    rate_used += 1
                    sleep(min(wait, RATE_WAIT_CAP_S))
                elif not exc.rate_limited and other_used < OTHER_RETRIES:
                    other_used += 1
                else:
                    break
    raise LlmError(f"Модель не дала корректный ответ ({last})")
