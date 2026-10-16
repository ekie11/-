"""Защита текста: исправление оформления не должно менять слова."""

import re

from .model import DocModel

_QUOTES = re.compile("[«»„“”\"']")
_DASHES = re.compile("[—–‑]")


class TextChangedError(Exception):
    """Текст документа изменился после исправления."""


def normalized_words(model: DocModel) -> list[str]:
    """Слова всех абзацев (включая таблицы): кавычки, тире, пробелы и регистр унифицированы; конечная точка абзаца не учитывается."""
    words: list[str] = []
    for p in model.paragraphs:
        text = _DASHES.sub("-", _QUOTES.sub('"', p.text)).casefold()
        # точка в конце абзаца: правило заголовков может её убрать
        words.extend(text.strip().removesuffix(".").split())
    return words
