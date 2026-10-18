"""Определение ролей абзацев по стилям и эвристикам."""

import re

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from .model import DocModel, DocParagraph, Role

STRUCTURAL_NAMES: frozenset[str] = frozenset(
    {
        "РЕФЕРАТ",
        "СОДЕРЖАНИЕ",
        "ТЕРМИНЫ И ОПРЕДЕЛЕНИЯ",
        "ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ",
        "ВВЕДЕНИЕ",
        "ЗАКЛЮЧЕНИЕ",
        "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ",
        "СПИСОК ЛИТЕРАТУРЫ",
        "БИБЛИОГРАФИЧЕСКИЙ СПИСОК",
        "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
        "ПРИЛОЖЕНИЕ",
    }
)

REFERENCE_TITLES: frozenset[str] = frozenset(
    {
        "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ",
        "СПИСОК ЛИТЕРАТУРЫ",
        "БИБЛИОГРАФИЧЕСКИЙ СПИСОК",
        "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
    }
)
_REF_ENTRY = re.compile(r"^\s*\d{1,3}[.)]\s")
_APPENDIX = re.compile(r"^ПРИЛОЖЕНИЕ\s+[А-ЯЁA-Z]$")
_FIGURE = re.compile(r"^(Рисунок\s+\d|Рис\.\s*\d)", re.IGNORECASE)
_TABLE = re.compile(r"^Таблица\s+\d", re.IGNORECASE)
_NUMBERED = re.compile(r"^(\d+(?:\.\d+){0,2})\.?\s+\S")
_HEADING_STYLE = re.compile(r"^(?:heading|заголовок)\s*(\d)$", re.IGNORECASE)
_LIST_STYLE = re.compile(r"^(?:list|список)", re.IGNORECASE)
_HEADING_ROLES = {1: Role.HEADING_1, 2: Role.HEADING_2, 3: Role.HEADING_3}


def _is_structural(text: str) -> bool:
    norm = " ".join(text.split()).upper()
    return norm in STRUCTURAL_NAMES or bool(_APPENDIX.match(norm))


def classify_text(text: str, bold: bool) -> Role | None:
    """Роль только по тексту (и жирности); None, если текст сам не решает."""
    t = text.strip()
    if not t:
        return None
    if _is_structural(t):
        return Role.STRUCTURAL
    if _FIGURE.match(t):
        return Role.FIGURE_CAPTION
    if _TABLE.match(t):
        return Role.TABLE_CAPTION
    m = _NUMBERED.match(t)
    if m and len(t) < 200 and (bold or (len(t) < 100 and not t.endswith("."))):
        return _HEADING_ROLES[m.group(1).count(".") + 1]
    return None


def _style_bold(para: Paragraph):
    style = para.style
    while style is not None:
        if style.font.bold is not None:
            return style.font.bold
        style = style.base_style
    return None


def _is_bold(para: Paragraph) -> bool:
    runs = [r for r in para.runs if r.text.strip()]
    if not runs:
        return False
    inherited = _style_bold(para)
    return all(r.bold if r.bold is not None else bool(inherited) for r in runs)


def _style_heading_role(para: Paragraph) -> Role | None:
    name = para.style.name or ""
    m = _HEADING_STYLE.match(name.strip())
    return _HEADING_ROLES.get(int(m.group(1))) if m else None


def _is_list(para: Paragraph) -> bool:
    name = para.style.name or ""
    if _LIST_STYLE.match(name):
        return True
    ppr = para._p.pPr
    return ppr is not None and ppr.find(qn("w:numPr")) is not None


def _iter_paragraphs(doc):
    parent = doc._body
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent), False
        elif child.tag == qn("w:tbl"):
            for p in child.iter(qn("w:p")):
                yield Paragraph(p, parent), True


def analyze(doc) -> DocModel:
    items: list[DocParagraph] = []
    style_based: set[int] = set()
    for i, (para, in_table) in enumerate(_iter_paragraphs(doc)):
        text = para.text
        if in_table:
            role = Role.IN_TABLE
        elif not text.strip():
            role = Role.EMPTY
        else:
            by_text = classify_text(text, _is_bold(para))
            by_style = _style_heading_role(para)
            if by_text == Role.STRUCTURAL:
                role = Role.STRUCTURAL
            elif by_style is not None:
                role = by_style
                style_based.add(i)
            elif by_text is not None:
                role = by_text
            elif _is_list(para):
                role = Role.LIST_ITEM
            else:
                role = Role.BODY
        items.append(DocParagraph(i, role, text, para))

    def norm(p: DocParagraph) -> str:
        return " ".join(p.text.split()).upper()

    # Титульный лист
    first = next(
        (p.index for p in items if p.role in (Role.STRUCTURAL, Role.HEADING_1)), None
    )
    has_marker = any(p.role == Role.STRUCTURAL and norm(p) in ("СОДЕРЖАНИЕ", "РЕФЕРАТ") for p in items)
    if first is not None and has_marker:
        for p in items[:first]:
            if p.role not in (Role.EMPTY, Role.IN_TABLE):
                p.role = Role.TITLE_PAGE

    # Оглавление
    toc_start = next(
        (p.index for p in items if p.role == Role.STRUCTURAL and norm(p) == "СОДЕРЖАНИЕ"),
        None,
    )
    if toc_start is not None:
        for p in items[toc_start + 1 :]:
            if p.role == Role.STRUCTURAL or p.index in style_based:
                break
            if p.role not in (Role.EMPTY, Role.IN_TABLE):
                p.role = Role.TOC

    # Записи списка источников («1. Иванов …») — не заголовки
    in_refs = False
    for p in items:
        if p.role == Role.STRUCTURAL:
            in_refs = norm(p) in REFERENCE_TITLES
        elif (in_refs and _REF_ENTRY.match(p.text)
              and p.role in (Role.HEADING_1, Role.HEADING_2, Role.HEADING_3)):
            p.role = Role.LIST_ITEM
    return DocModel(doc=doc, paragraphs=items)
