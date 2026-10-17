"""Правило нумерации страниц: поле PAGE в нижнем колонтитуле."""

import re

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from ..model import DocModel
from ..profile import RuleConfig
from ..units import _style_chain
from .base import Issue, Rule, register

_PAGE_FIELD = re.compile(r"^\s*PAGE\b", re.IGNORECASE)
_ALIGN_NAMES = {"justify": "по ширине", "left": "по левому краю",
                "center": "по центру", "right": "по правому краю"}


def _has_page_field(par) -> bool:
    if any(_PAGE_FIELD.match(t.text or "") for t in par._p.xpath(".//w:instrText")):
        return True
    return any(_PAGE_FIELD.match(f.get(qn("w:instr")) or "") for f in par._p.xpath(".//w:fldSimple"))


def _alignment(par) -> str:
    """Выравнивание абзаца колонтитула (части стилей документа у колонтитула нет)."""
    ppr = par._p.pPr
    chain = [ppr] + [st.element.pPr for st in _style_chain(par)]
    for pr in chain:
        jc = pr.find(qn("w:jc")) if pr is not None else None
        if jc is not None:
            return {"both": "justify", "center": "center", "right": "right",
                    "end": "right"}.get(jc.get(qn("w:val")), "left")
    return "left"


def _field_paragraph(footer):
    return next((p for p in footer.paragraphs if _has_page_field(p)), None)


def _own_footer_sections(model: DocModel):
    """Разделы с собственным колонтитулом (первый раздел — всегда)."""
    for i, s in enumerate(model.doc.sections):
        if i == 0 or not s.footer.is_linked_to_previous:
            yield i, s


@register
class PageNumbersRule(Rule):
    key = "page_numbers"
    fixable = True

    def _issue(self, cfg, msg, exp, act):
        return Issue(rule=self.key, source=cfg.source, severity=cfg.severity, message=msg,
                     expected=exp, actual=act, paragraph_index=None, fixable=True)

    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        issues = []
        for i, s in _own_footer_sections(model):
            where = f" (раздел {i + 1})" if len(model.doc.sections) > 1 else ""
            par = _field_paragraph(s.footer)
            if par is None:
                issues.append(self._issue(
                    cfg, f"Номер страницы{where}: ожидается внизу страницы, найден отсутствует",
                    "внизу страницы", "отсутствует"))
            else:
                act = _alignment(par)
                if act != "center":
                    e, a = _ALIGN_NAMES["center"], _ALIGN_NAMES[act]
                    issues.append(self._issue(
                        cfg, f"Номер страницы{where}: ожидается выравнивание {e}, найдено {a}", e, a))
            if par is not None and i == 0 and not cfg.value.get("show_on_first", False) \
                    and not s.different_first_page_header_footer:
                issues.append(self._issue(
                    cfg, "Номер на первой странице: ожидается скрыт, найден показан",
                    "скрыт", "показан"))
        return issues

    def fix(self, model: DocModel, cfg: RuleConfig) -> None:
        for i, s in _own_footer_sections(model):
            footer = s.footer
            if i == 0 and footer.is_linked_to_previous:
                footer.is_linked_to_previous = False
            par = _field_paragraph(footer)
            if par is None:
                par = footer.paragraphs[0]
                run = par.add_run()
                for kind, text in (("begin", None), (None, " PAGE "), ("end", None)):
                    if kind:
                        el = OxmlElement("w:fldChar")
                        el.set(qn("w:fldCharType"), kind)
                    else:
                        el = OxmlElement("w:instrText")
                        el.set(qn("xml:space"), "preserve")
                        el.text = text
                    run._r.append(el)
            if _alignment(par) != "center":
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if i == 0 and not cfg.value.get("show_on_first", False):
                s.different_first_page_header_footer = True
