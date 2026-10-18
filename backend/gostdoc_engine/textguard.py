"""Защита текста: исправление оформления не должно менять слова."""

import re

from .model import DocModel, Role

_LENIENT = {Role.HEADING_1, Role.HEADING_2, Role.HEADING_3, Role.STRUCTURAL}

_QUOTES = re.compile("[«»„“”\"']")
_SEP = re.compile(r"(//|:)")
_DASHES = re.compile("[—–‑]")


class TextChangedError(Exception):
    """Текст документа изменился после исправления."""


def normalized_words(model: DocModel) -> list[str]:
    """Слова всех абзацев (включая таблицы): кавычки, тире, пробелы и регистр унифицированы; конечная точка не учитывается только у заголовков."""
    words: list[str] = []
    for p in model.paragraphs:
        text = _DASHES.sub("-", _QUOTES.sub('"', p.text)).casefold()
        # типографика записей: «//» и «:» могут получить пробелы вокруг
        text = _SEP.sub(r" \1 ", text)
        # точка в конце: правило заголовков может её убрать
        text = text.strip()
        if p.role in _LENIENT:
            text = text.removesuffix(".")
        words.extend(text.split())
    return words
