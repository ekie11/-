"""Разбор списка источников и проверка записей (ГОСТ Р 7.0.100-2018)."""

import re
from dataclasses import dataclass

from .model import DocModel, DocParagraph, Role

SECTION_TITLES: frozenset[str] = frozenset(
    {
        "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ",
        "СПИСОК ЛИТЕРАТУРЫ",
        "БИБЛИОГРАФИЧЕСКИЙ СПИСОК",
        "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
    }
)

_NUM_START = re.compile(r"^\s*(\d+)[.)]\s")
_YEAR = re.compile(r"\b(1[89]|20)\d{2}\b")
_ACCESS = re.compile(r"\(дата обращения:\s*\d{2}\.\d{2}\.\d{4}\)", re.IGNORECASE)
_OLD_ELECTRONIC = re.compile(r"\[Электронный ресурс\]", re.IGNORECASE)


@dataclass
class Entry:
    number: int | None
    text: str
    paragraph_index: int


def _norm(text: str) -> str:
    return " ".join(text.split()).upper()


def find_section(model: DocModel) -> list[DocParagraph] | None:
    start = next(
        (i for i, p in enumerate(model.paragraphs)
         if p.role != Role.IN_TABLE and _norm(p.text) in SECTION_TITLES),
        None,
    )
    if start is None:
        return None
    out = []
    for p in model.paragraphs[start + 1:]:
        if p.role == Role.STRUCTURAL:
            break
        if p.role not in (Role.EMPTY, Role.IN_TABLE):
            out.append(p)
    return out


def parse_entries(paragraphs: list[DocParagraph]) -> list[Entry]:
    entries: list[Entry] = []
    for p in paragraphs:
        m = _NUM_START.match(p.text)
        if m or p.role == Role.LIST_ITEM or not entries:
            entries.append(Entry(int(m.group(1)) if m else None, p.text.strip(), p.index))
        else:
            entries[-1].text += " " + p.text.strip()
    return entries


def check_entry(entry: Entry) -> list[str]:
    label = f"Источник {entry.number}"
    text = entry.text
    msgs = []
    if not _YEAR.search(text):
        msgs.append(f"{label}: нет года издания")
    electronic = "URL:" in text or "http" in text
    if electronic:
        if not _ACCESS.search(text):
            msgs.append(f"{label}: у электронного ресурса нет даты обращения")
    elif " // " not in text and not (" — " in text and " : " in text):
        msgs.append(f"{label}: нет выходных данных (« — Место : Издательство, год» "
                    "или « // Источник» для статьи)")
    if _OLD_ELECTRONIC.search(text):
        msgs.append(f"{label}: используйте «Текст : электронный» вместо «[Электронный ресурс]»")
    return msgs
