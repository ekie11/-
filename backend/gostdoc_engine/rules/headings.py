"""Правила заголовков: разделов (HEADING_1..3) и структурных элементов (STRUCTURAL)."""

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm

from .. import units
from ..analyze import _style_bold
from ..model import DocModel, DocParagraph, Role
from ..profile import RuleConfig
from .base import Issue, Rule, register

_INDENT_TOL_CM = 0.05
_ALIGN_NAMES = {
    "justify": "по ширине",
    "left": "по левому краю",
    "center": "по центру",
    "right": "по правому краю",
}
_ALIGN_ENUM = {
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
}


def _is_bold(par) -> bool:
    inherited = bool(_style_bold(par))
    runs = [r for r in units.all_runs(par) if r.text.strip()]
    return bool(runs) and all(r.bold if r.bold is not None else inherited for r in runs)


def _page_break_before(par) -> bool:
    ppr = par._p.pPr
    if ppr is not None:
        el = ppr.find(qn("w:pageBreakBefore"))
        if el is not None:
            return el.get(qn("w:val")) not in ("0", "false", "off")
    for style in units._style_chain(par):
        value = style.paragraph_format.page_break_before
        if value is not None:
            return value
    return False


def _strip_trailing_period(par) -> None:
    texts = [t for t in par._p.xpath(".//w:t") if t.text and t.text.strip()]
    if texts and texts[-1].text.rstrip().endswith("."):
        t = texts[-1]
        t.text = t.text.rstrip()[:-1]


class _HeadingRule(Rule):
    fixable = True
    roles: tuple[Role, ...]
    indent_roles: tuple[Role, ...] = ()

    def _page_break_expected(self, p: DocParagraph, cfg: RuleConfig) -> bool:
        raise NotImplementedError

    def _violations(self, p: DocParagraph, cfg: RuleConfig):
        """Список (код, сообщение, ожидается, найдено)."""
        v = cfg.value
        par = p.para
        out = []
        if v.get("bold") and not _is_bold(par):
            out.append(
                (
                    "bold",
                    "Заголовок: ожидается полужирное начертание, найдено обычное",
                    "полужирное",
                    "обычное",
                )
            )
        align = v.get("align")
        if align:
            act = units.effective_alignment(par)
            if act != align:
                e, a = _ALIGN_NAMES[align], _ALIGN_NAMES[act]
                out.append(("align", f"Заголовок: ожидается выравнивание {e}, найдено {a}", e, a))
        indent = v.get("first_line_indent_cm")
        if indent is not None and p.role in self.indent_roles:
            act = units.effective_first_line_indent_cm(par)
            if abs(act - indent) > _INDENT_TOL_CM:
                e, a = f"{units.fmt_num(indent)} см", f"{units.fmt_num(act)} см"
                out.append(
                    ("indent", f"Заголовок: ожидается абзацный отступ {e}, найдено {a}", e, a)
                )
        if v.get("trailing_period") is False and p.text.rstrip().endswith("."):
            out.append(
                (
                    "period",
                    "Заголовок: ожидается без точки в конце",
                    "без точки в конце",
                    "точка в конце",
                )
            )
        if v.get("uppercase") and p.text != p.text.upper():
            out.append(
                (
                    "upper",
                    "Заголовок: ожидается прописными буквами",
                    "прописными буквами",
                    "не прописными буквами",
                )
            )
        if self._page_break_expected(p, cfg) and not _page_break_before(par):
            out.append(
                (
                    "break",
                    "Заголовок: ожидается начало с новой страницы",
                    "с новой страницы",
                    "без разрыва страницы",
                )
            )
        return out

    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        issues = []
        for p in model.by_role(*self.roles):
            for _code, msg, exp, act in self._violations(p, cfg):
                issues.append(
                    Issue(
                        rule=self.key,
                        source=cfg.source,
                        severity=cfg.severity,
                        message=msg,
                        expected=exp,
                        actual=act,
                        paragraph_index=p.index,
                        fixable=True,
                    )
                )
        return issues

    def fix(self, model: DocModel, cfg: RuleConfig) -> None:
        for p in model.by_role(*self.roles):
            par = p.para
            for code, *_ in self._violations(p, cfg):
                if code == "bold":
                    for run in units.all_runs(par):
                        run.bold = True
                elif code == "align":
                    par.alignment = _ALIGN_ENUM[cfg.value["align"]]
                elif code == "indent":
                    par.paragraph_format.first_line_indent = Cm(cfg.value["first_line_indent_cm"])
                elif code == "period":
                    _strip_trailing_period(par)
                elif code == "upper":
                    for t in par._p.xpath(".//w:t"):
                        if t.text:
                            t.text = t.text.upper()
                elif code == "break":
                    par.paragraph_format.page_break_before = True


@register
class SectionHeadingRule(_HeadingRule):
    key = "headings.section"
    roles = (Role.HEADING_1, Role.HEADING_2, Role.HEADING_3)
    indent_roles = roles

    def _page_break_expected(self, p, cfg):
        return bool(cfg.value.get("page_break_before_level1")) and p.role == Role.HEADING_1


@register
class StructuralHeadingRule(_HeadingRule):
    key = "headings.structural"
    roles = (Role.STRUCTURAL,)

    def _page_break_expected(self, p, cfg):
        return bool(cfg.value.get("page_break_before"))
