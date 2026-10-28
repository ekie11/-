"""Правила основного текста (роли BODY и LIST_ITEM)."""

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from .. import units
from ..model import DocModel, DocParagraph, Role
from ..profile import RuleConfig
from .base import Issue, Rule, register

_SPACING_TOL = 0.05
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


def _targets(model: DocModel, with_list: bool = True) -> list[DocParagraph]:
    roles = (Role.BODY, Role.LIST_ITEM) if with_list else (Role.BODY,)
    return model.by_role(*roles)


def _issue(rule: Rule, cfg: RuleConfig, p: DocParagraph, message: str, exp: str, act: str) -> Issue:
    return Issue(
        rule=rule.key,
        source=cfg.source,
        severity=cfg.severity,
        message=message,
        expected=exp,
        actual=act,
        paragraph_index=p.index,
        fixable=True,
    )


@register
class FontNameRule(Rule):
    key = "body.font_name"
    fixable = True

    def check(self, model, cfg):
        exp = cfg.value["name"]
        issues = []
        for p in _targets(model):
            act = units.effective_font_name(p.para)
            if act != exp:
                shown = act or "не задан"
                issues.append(
                    _issue(self, cfg, p, f"Шрифт: ожидается {exp}, найден {shown}", exp, shown)
                )
        return issues

    def fix(self, model, cfg):
        exp = cfg.value["name"]
        for p in _targets(model):
            if units.effective_font_name(p.para) == exp:
                continue
            for run in units.all_runs(p.para):
                run.font.name = exp
                rf = run._r.rPr.find(qn("w:rFonts"))
                for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
                    if rf.get(qn(attr)) is not None:
                        del rf.attrib[qn(attr)]
                for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                    rf.set(qn(attr), exp)


@register
class FontSizeRule(Rule):
    key = "body.font_size"
    fixable = True

    def check(self, model, cfg):
        min_pt = cfg.value["min_pt"]
        issues = []
        for p in _targets(model):
            act = units.effective_font_size_pt(p.para)
            if act is not None and act < min_pt:
                e, a = f"не менее {units.fmt_num(min_pt)} пт", f"{units.fmt_num(act)} пт"
                issues.append(
                    _issue(self, cfg, p, f"Размер шрифта: ожидается {e}, найдено {a}", e, a)
                )
        return issues

    def fix(self, model, cfg):
        min_pt, target = cfg.value["min_pt"], cfg.value["target_pt"]
        for p in _targets(model):
            act = units.effective_font_size_pt(p.para)
            if act is None or act >= min_pt:
                continue
            for run in units.all_runs(p.para):
                run.font.size = Pt(target)
                rpr = run._r.rPr
                for el in rpr.findall(qn("w:szCs")):
                    rpr.remove(el)
                szcs = rpr.makeelement(qn("w:szCs"), {qn("w:val"): str(int(target * 2))})
                rpr.find(qn("w:sz")).addnext(szcs)


@register
class LineSpacingRule(Rule):
    key = "body.line_spacing"
    fixable = True

    def _ok(self, par, exp):
        act = units.effective_line_spacing(par)
        return act is not None and abs(act - exp) <= _SPACING_TOL, act

    def check(self, model, cfg):
        exp = cfg.value["multiple"]
        issues = []
        for p in _targets(model):
            ok, act = self._ok(p.para, exp)
            if not ok:
                a = units.fmt_num(act) if act is not None else "фиксированный"
                issues.append(
                    _issue(
                        self,
                        cfg,
                        p,
                        f"Межстрочный интервал: ожидается {units.fmt_num(exp)}, найдено {a}",
                        units.fmt_num(exp),
                        a,
                    )
                )
        return issues

    def fix(self, model, cfg):
        exp = cfg.value["multiple"]
        for p in _targets(model):
            if not self._ok(p.para, exp)[0]:
                pf = p.para.paragraph_format
                pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
                pf.line_spacing = exp


@register
class FirstLineIndentRule(Rule):
    key = "body.first_line_indent"
    fixable = True

    def check(self, model, cfg):
        exp = cfg.value["cm"]
        issues = []
        for p in _targets(model, with_list=False):
            act = units.effective_first_line_indent_cm(p.para)
            if abs(act - exp) > _INDENT_TOL_CM:
                e, a = f"{units.fmt_num(exp)} см", f"{units.fmt_num(act)} см"
                issues.append(
                    _issue(self, cfg, p, f"Абзацный отступ: ожидается {e}, найдено {a}", e, a)
                )
        return issues

    def fix(self, model, cfg):
        exp = cfg.value["cm"]
        for p in _targets(model, with_list=False):
            if abs(units.effective_first_line_indent_cm(p.para) - exp) > _INDENT_TOL_CM:
                p.para.paragraph_format.first_line_indent = Cm(exp)


@register
class AlignmentRule(Rule):
    key = "body.alignment"
    fixable = True

    def check(self, model, cfg):
        exp = cfg.value["align"]
        issues = []
        for p in _targets(model):
            act = units.effective_alignment(p.para)
            if act != exp:
                e, a = _ALIGN_NAMES[exp], _ALIGN_NAMES[act]
                issues.append(
                    _issue(self, cfg, p, f"Выравнивание: ожидается {e}, найдено {a}", e, a)
                )
        return issues

    def fix(self, model, cfg):
        exp = cfg.value["align"]
        for p in _targets(model):
            if units.effective_alignment(p.para) != exp:
                p.para.alignment = _ALIGN_ENUM[exp]
