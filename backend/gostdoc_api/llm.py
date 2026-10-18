"""Клиент OpenAI-совместимой модели: один запрос, ответ — JSON-объект."""

from __future__ import annotations

import json
import re

import httpx

from .config import Settings

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class LlmError(Exception):
    """Модель недоступна или вернула непригодный ответ."""


class _Retry(Exception):
    pass


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
    if resp.status_code >= 500 or resp.status_code == 429:
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
    with httpx.Client(timeout=settings.llm_timeout_s, transport=transport) as client:
        for _ in range(2):
            try:
                return _once(client, url, headers, body)
            except _Retry as exc:
                last = str(exc)
    raise LlmError(f"Модель не дала корректный ответ ({last})")
