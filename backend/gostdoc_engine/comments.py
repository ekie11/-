"""Замечания как комментарии Word: один комментарий на абзац."""

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.text.run import Run

from .model import DocModel, DocParagraph
from .rules.base import Issue

AUTHOR = "ГОСТ-сервис"
INITIALS = "ГС"


def remove_service_comments(doc) -> int:
    """Удалить комментарии «ГОСТ-сервис» и их привязки; вернуть число удалённых."""
    try:
        part = doc.part.part_related_by(RT.COMMENTS)
    except KeyError:
        return 0
    root = part.element
    ids = {
        c.get(qn("w:id"))
        for c in root.findall(qn("w:comment"))
        if c.get(qn("w:author")) == AUTHOR
    }
    if not ids:
        return 0
    for c in list(root.findall(qn("w:comment"))):
        if c.get(qn("w:id")) in ids:
            root.remove(c)
    body = doc.element.body
    for tag in ("w:commentRangeStart", "w:commentRangeEnd"):
        for el in body.iter(qn(tag)):
            if el.get(qn("w:id")) in ids:
                el.getparent().remove(el)
    for ref in list(body.iter(qn("w:commentReference"))):
        if ref.get(qn("w:id")) not in ids:
            continue
        run = ref.getparent()
        run.remove(ref)
        meaningful = [ch for ch in run if ch.tag != qn("w:rPr")]
        if not meaningful and run.getparent() is not None:
            run.getparent().remove(run)
    return len(ids)


def _first_non_empty(model: DocModel) -> DocParagraph | None:
    return next((p for p in model.paragraphs if p.text.strip()), None)


def add_comments(model: DocModel, issues: list[Issue]) -> int:
    """Добавить комментарии Word к абзацам; вернуть их число.

    Замечания одного абзаца объединяются в один комментарий. Замечания без абзаца
    (например, page.*) относятся к первому непустому абзацу. Замечания к неизвестному
    абзацу пропускаются.
    """
    by_index = {p.index: p for p in model.paragraphs}
    first = _first_non_empty(model)
    grouped: dict[int, list[str]] = {}
    for item in issues:
        if item.paragraph_index is None:
            target = first
        else:
            target = by_index.get(item.paragraph_index)
        if target is None:
            continue
        grouped.setdefault(target.index, []).append(f"[{item.source}] {item.message}")

    for index, lines in grouped.items():
        par = by_index[index].para
        runs: list[Run] = list(par.runs)
        if not runs:
            runs = [par.add_run("")]
        model.doc.add_comment(runs, text="\n".join(lines), author=AUTHOR, initials=INITIALS)
    return len(grouped)
