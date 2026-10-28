"""Эффективные свойства абзаца: прямое форматирование → цепочка стилей → умолчания документа."""

from collections import Counter

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run

TWIPS_PER_CM = 566.929
EMU_PER_MM = 36000


def fmt_num(value: float, digits: int = 2) -> str:
    """Число с десятичной запятой, без лишних нулей."""
    return f"{round(value, digits):g}".replace(".", ",")


def all_runs(par: Paragraph) -> list[Run]:
    """Все w:r абзаца, включая вложенные (гиперссылки и т. п.)."""
    return [Run(r, par) for r in par._p.xpath(".//w:r")]


def _style_chain(par: Paragraph):
    style = par.style
    seen = 0
    while style is not None and seen < 50:
        yield style
        style = style.base_style
        seen += 1


def _doc_defaults(par: Paragraph, kind: str):
    """kind: 'rPr' или 'pPr'."""
    styles = par.part.styles.element
    res = styles.xpath(f"w:docDefaults/w:{kind}Default/w:{kind}")
    return res[0] if res else None


def _inherited_rpr(par: Paragraph, getter):
    for style in _style_chain(par):
        rpr = style.element.rPr
        if rpr is not None:
            value = getter(rpr)
            if value is not None:
                return value
    rpr = _doc_defaults(par, "rPr")
    return getter(rpr) if rpr is not None else None


def _rfonts_name(rpr):
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        return None
    return rf.get(qn("w:ascii")) or rf.get(qn("w:hAnsi"))


def _sz_pt(rpr):
    sz = rpr.find(qn("w:sz"))
    if sz is None:
        return None
    return int(sz.get(qn("w:val"))) / 2


def _dominant(par: Paragraph, run_getter, inherited):
    counts: Counter = Counter()
    for run in all_runs(par):
        n = len(run.text.strip())
        if not n:
            continue
        rpr = run._r.rPr
        value = run_getter(rpr) if rpr is not None else None
        counts[value if value is not None else inherited] += n
    counts.pop(None, None)
    if counts:
        return counts.most_common(1)[0][0]
    return inherited


def effective_font_name(par: Paragraph) -> str | None:
    inherited = _inherited_rpr(par, _rfonts_name)
    return _dominant(par, _rfonts_name, inherited)


def effective_font_size_pt(par: Paragraph) -> float | None:
    inherited = _inherited_rpr(par, _sz_pt)
    return _dominant(par, _sz_pt, inherited)


def _inherited_ppr(par: Paragraph, getter):
    ppr = par._p.pPr
    if ppr is not None:
        value = getter(ppr)
        if value is not None:
            return value
    for style in _style_chain(par):
        ppr = style.element.pPr
        if ppr is not None:
            value = getter(ppr)
            if value is not None:
                return value
    ppr = _doc_defaults(par, "pPr")
    return getter(ppr) if ppr is not None else None


def _line(ppr):
    sp = ppr.find(qn("w:spacing"))
    if sp is None or sp.get(qn("w:line")) is None:
        return None
    rule = sp.get(qn("w:lineRule")) or "auto"
    return (rule, int(sp.get(qn("w:line"))))


def effective_line_spacing(par: Paragraph) -> float | None:
    """Множитель межстрочного интервала; None для «точно»/«минимум»."""
    value = _inherited_ppr(par, _line)
    if value is None:
        return 1.0
    rule, line = value
    return line / 240 if rule == "auto" else None


def _indent(ppr):
    ind = ppr.find(qn("w:ind"))
    if ind is None:
        return None
    first = ind.get(qn("w:firstLine"))
    hanging = ind.get(qn("w:hanging"))
    if first is not None:
        return int(first) / TWIPS_PER_CM
    if hanging is not None:
        return -int(hanging) / TWIPS_PER_CM
    return None


def effective_first_line_indent_cm(par: Paragraph) -> float:
    value = _inherited_ppr(par, _indent)
    return 0.0 if value is None else value


_JC = {
    "both": "justify",
    "distribute": "justify",
    "left": "left",
    "start": "left",
    "center": "center",
    "right": "right",
    "end": "right",
}


def _jc(ppr):
    jc = ppr.find(qn("w:jc"))
    return None if jc is None else _JC.get(jc.get(qn("w:val")), "left")


def effective_alignment(par: Paragraph) -> str:
    return _inherited_ppr(par, _jc) or "left"
