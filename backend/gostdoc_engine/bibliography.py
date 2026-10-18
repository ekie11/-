"""Разбор списка источников и проверка записей (ГОСТ Р 7.0.100-2018)."""

import re
from dataclasses import dataclass

from .analyze import REFERENCE_TITLES as SECTION_TITLES
from .model import DocModel, DocParagraph, Role

_NUM_START = re.compile(r"^\s*(\d{1,3})[.)]\s")
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
    start = max(
        (i for i, p in enumerate(model.paragraphs)
         if p.role == Role.STRUCTURAL and _norm(p.text) in SECTION_TITLES),
        default=None,
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
        num = int(m.group(1)) if m else None
        prev = entries[-1].number if entries else None
        if num is not None:
            starts = prev is None or num > prev
        else:
            starts = not entries or p.role == Role.LIST_ITEM
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


_CITE = re.compile(r"\[(\d[^\[\]]*)\]")
_CITE_PART = re.compile(r"\s*(\d{1,3})(?:\s*[–-]\s*(\d{1,3}))?\s*")
MAX_RANGE = 50


def _cite_numbers(body: str) -> list[int]:
    nums: list[int] = []
    for part in re.split(r"[;,]", body):
        m = _CITE_PART.fullmatch(part)
        if not m:
            continue
        lo = int(m.group(1))
        if lo < 1:
            continue
        if m.group(2) is None:
            nums.append(lo)
            continue
        hi = int(m.group(2))
        if lo <= hi and hi - lo + 1 <= MAX_RANGE:
            nums.extend(range(lo, hi + 1))
        else:
            nums.extend([lo, hi])
    return nums


def find_citations(model: DocModel) -> list[tuple[int, list[int]]]:
    """Ссылки [N], [N, с. X], [N; M], [N–M] вне списка источников и оглавления."""
    section = find_section(model) or []
    skip = {p.index for p in section}
    out = []
    for p in model.paragraphs:
        if p.index in skip or p.role in (Role.TOC, Role.EMPTY, Role.TITLE_PAGE,
                          Role.FIGURE_CAPTION, Role.TABLE_CAPTION):
            continue
        nums = [n for m in _CITE.finditer(p.text) for n in _cite_numbers(m.group(1))]
        if nums:
            out.append((p.index, nums))
    return out


def _replace_span(ts, start: int, end: int, repl: str) -> None:
    """Заменить символы [start, end) сквозь w:t соседних прогонов (end > start)."""
    pos = 0
    placed = False
    for t in ts:
        txt = t.text or ""
        a, b = max(start - pos, 0), min(end - pos, len(txt))
        if a < b:
            t.text = txt[:a] + (repl if not placed else "") + txt[b:]
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            placed = True
        pos += len(txt)


def _dash_repl(m: re.Match) -> str | None:
    text = m.string
    if text[max(m.start() - 2, 0):m.start() - 1].isdigit() and text[m.end() + 1:m.end() + 2].isdigit():
        return None  # диапазон «10 - 15» не трогаем
    return "—"


_MASK = re.compile(r"\bhttps?://\S+|\b\S+@\S+\.\S+|mailto:\S+")


def fix_paragraph_typography(par) -> None:
    """Пробелы и тире между элементами записи; работает сквозь прогоны."""
    ts = par._p.xpath(".//w:t")
    passes = [
        (re.compile(r" {2,}"), lambda m: " "),
        (re.compile(r"(?<=\s)[-–](?=\s)"), _dash_repl),
        (re.compile(r"(?<=\.)[-–](?=\s)"), lambda m: " —"),
        (re.compile(r"\s+—\s*|\s*—\s+"), lambda m: " — "),
        (re.compile(r"(?<![:/])\s*//(?!/)\s*"), lambda m: " // "),
        (re.compile(r"(?<=[а-яёА-ЯЁ.])(?: :|:)(?=[а-яёА-ЯЁ])"), lambda m: " : "),
        (re.compile(r" {2,}"), lambda m: " "),
    ]
    for n, (rx, fn) in enumerate(passes):
        full = "".join(t.text or "" for t in ts)
        masked = [m.span() for m in _MASK.finditer(full)] if 4 <= n <= 5 else []
        edits = []
        for m in rx.finditer(full):
            if any(m.start() < b and a < m.end() for a, b in masked):
                continue
            repl = fn(m)
            if repl is not None and repl != m.group(0):
                edits.append((m.start(), m.end(), repl))
        for a, b, repl in reversed(edits):
            _replace_span(ts, a, b, repl)
