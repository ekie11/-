"""Разбор списка источников и проверка записей (ГОСТ Р 7.0.100-2018)."""

import re
from dataclasses import dataclass

from .analyze import REFERENCE_TITLES as SECTION_TITLES
from .model import DocModel, DocParagraph, Role

_NUM_START = re.compile(r"^\s*(\d+)[.)]\s")
_YEAR = re.compile(r"\b(1[89]|20)\d{2}\b")
_ACCESS = re.compile(r"\(дата обращения:\s*\d{2}\.\d{2}\.\d{4}\)", re.IGNORECASE)
_URL = re.compile(r"https?://|URL:")
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
         if p.role == Role.STRUCTURAL and _norm(p.text) in SECTION_TITLES),
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


def _complete(text: str) -> bool:
    return text.rstrip().endswith((".", ";"))


def parse_entries(paragraphs: list[DocParagraph]) -> list[Entry]:
    entries: list[Entry] = []
    for p in paragraphs:
        m = _NUM_START.match(p.text)
        num = int(m.group(1)) if m else None
        prev = entries[-1].number if entries else None
        starts = (
            not entries
            or p.role == Role.LIST_ITEM
            or (num is not None and num <= 999 and (prev is None or num == prev + 1 or _complete(entries[-1].text)))
        )
        if starts:
            entries.append(Entry(num, p.text.strip(), p.index))
        else:
            entries[-1].text += " " + p.text.strip()
    return entries


def check_entry(entry: Entry) -> list[str]:
    label = f"Источник {entry.number}"
    text = entry.text
    msgs = []
    if not _YEAR.search(text):
        msgs.append(f"{label}: нет года издания")
    electronic = bool(_URL.search(text))
    if electronic:
        if not _ACCESS.search(text):
            msgs.append(f"{label}: у электронного ресурса нет даты обращения")
    elif " // " not in text and not (" — " in text and " : " in text):
        msgs.append(f"{label}: нет выходных данных (« — Место : Издательство, год» "
                    "или « // Источник» для статьи)")
    if _OLD_ELECTRONIC.search(text):
        msgs.append(f"{label}: используйте «Текст : электронный» вместо «[Электронный ресурс]»")
    return msgs
