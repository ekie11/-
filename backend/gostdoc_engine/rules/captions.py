"""Правила подписей к рисункам и таблицам."""

import re

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm

from .. import units
from ..model import DocModel, DocParagraph, Role
from ..profile import RuleConfig
from .base import Issue, Rule, register

_DASHES = "—–-"
_INDENT_TOL_CM = 0.05
_ALIGN_NAMES = {"justify": "по ширине", "left": "по левому краю",
                "center": "по центру", "right": "по правому краю"}
_ALIGN_ENUM = {"justify": WD_ALIGN_PARAGRAPH.JUSTIFY, "left": WD_ALIGN_PARAGRAPH.LEFT,
               "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT}
_NUM = r"[\dА-ЯA-Z]+(?:\.\d+)*"


def _regex(pattern: str) -> re.Pattern:
    out = []
    for part in re.split(rf"(\{{n\}}|\{{title\}}|\s+|[{_DASHES}])", pattern):
        if part == "{n}":
            out.append(_NUM)
        elif part == "{title}":
            out.append(r".+")
        elif part and part in _DASHES:
            out.append(f"(?P<dash>[{_DASHES}])")
        elif part and part.isspace():
            out.append(r"\s+")
        else:
            out.append(re.escape(part))
    return re.compile("^" + "".join(out) + "$", re.DOTALL)


def _expected_dash(pattern: str) -> str:
    return next((c for c in pattern if c in _DASHES), "—")


def _text(par) -> str:
    return "".join(t.text or "" for t in par._p.xpath(".//w:t"))


def _has_drawing(p: DocParagraph) -> bool:
    return p.role != Role.IN_TABLE and bool(p.para._p.xpath(".//w:drawing"))


class _CaptionRule(Rule):
    fixable = True
    role: Role
    label: str  # "рисунка" / "таблицы"

    def _targets(self, model: DocModel) -> list[DocParagraph]:
        return model.by_role(self.role)

    def _position_ok(self, model: DocModel, p: DocParagraph) -> bool:
        raise NotImplementedError

    def _position_msg(self) -> tuple[str, str, str]:
        raise NotImplementedError

    def _problems(self, model: DocModel, p: DocParagraph, cfg: RuleConfig):
        """(код, сообщение, ожидается, найдено, исправимо)."""
        v = cfg.value
        out = []
        pattern = v["pattern"]
        exp_dash = _expected_dash(pattern)
        m = _regex(pattern).match(_text(p.para).strip())
        name = f"Подпись {self.label}"
        if m is None:
            out.append(("pattern", f"{name}: ожидается формат «{pattern}»",
                        pattern, _text(p.para).strip(), False))
        elif m.group("dash") != exp_dash:
            act = m.group("dash")
            out.append(("dash", f"{name}: ожидается тире «{exp_dash}», найдено «{act}»",
                        f"«{exp_dash}»", f"«{act}»", True))
        align = v.get("align")
        if align:
            act = units.effective_alignment(p.para)
            if act != align:
                e, a = _ALIGN_NAMES[align], _ALIGN_NAMES[act]
                out.append(("align", f"{name}: ожидается выравнивание {e}, найдено {a}", e, a, True))
        indent = v.get("first_line_indent_cm")
        if indent is not None:
            act = units.effective_first_line_indent_cm(p.para)
            if abs(act - indent) > _INDENT_TOL_CM:
                e, a = f"{units.fmt_num(indent)} см", f"{units.fmt_num(act)} см"
                out.append(("indent", f"{name}: ожидается абзацный отступ {e}, найдено {a}", e, a, True))
        if not self._position_ok(model, p):
            msg, e, a = self._position_msg()
            out.append(("position", msg, e, a, False))
        return out

    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        issues = []
        for p in self._targets(model):
            for _c, msg, exp, act, fixable in self._problems(model, p, cfg):
                issues.append(Issue(rule=self.key, source=cfg.source, severity=cfg.severity,
                                    message=msg, expected=exp, actual=act,
                                    paragraph_index=p.index, fixable=fixable))
        return issues

    def fix(self, model: DocModel, cfg: RuleConfig) -> None:
        v = cfg.value
        for p in self._targets(model):
            for code, *_ in self._problems(model, p, cfg):
                if code == "dash":
                    self._fix_dash(p.para, _expected_dash(v["pattern"]), _regex(v["pattern"]))
                elif code == "align":
                    p.para.alignment = _ALIGN_ENUM[v["align"]]
                elif code == "indent":
                    p.para.paragraph_format.first_line_indent = Cm(v["first_line_indent_cm"])

    @staticmethod
    def _fix_dash(par, dash: str, regex: re.Pattern) -> None:
        ts = par._p.xpath(".//w:t")
        full = "".join(t.text or "" for t in ts)
        lead = len(full) - len(full.lstrip())
        m = regex.match(full.strip())
        if m is None:
            return
        pos = lead + m.start("dash")
        for t in ts:
            n = len(t.text or "")
            if pos < n:
                t.text = t.text[:pos] + dash + t.text[pos + 1:]
                return
            pos -= n


@register
class FigureCaptionRule(_CaptionRule):
    key = "captions.figure"
    role = Role.FIGURE_CAPTION
    label = "рисунка"

    def _position_ok(self, model, p):
        prev = next((q for q in reversed(model.paragraphs[: p.index])
                     if q.role != Role.EMPTY or _has_drawing(q)), None)
        return prev is not None and _has_drawing(prev)

    def _position_msg(self):
        return ("Подпись рисунка: ожидается под рисунком, найдена не под рисунком",
                "под рисунком", "не под рисунком")


@register
class TableCaptionRule(_CaptionRule):
    key = "captions.table"
    role = Role.TABLE_CAPTION
    label = "таблицы"

    def _position_ok(self, model, p):
        el = p.para._p.getnext()
        while el is not None and el.tag not in (qn("w:p"), qn("w:tbl")):
            el = el.getnext()
        return el is not None and el.tag == qn("w:tbl")

    def _position_msg(self):
        return ("Подпись таблицы: ожидается над таблицей, найдена не над таблицей",
                "над таблицей", "не над таблицей")
