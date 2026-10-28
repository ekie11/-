"""Правила страницы: формат и поля."""

from docx.enum.section import WD_ORIENT
from docx.shared import Mm

from ..model import DocModel
from ..profile import RuleConfig
from ..units import EMU_PER_MM, fmt_num
from .base import Issue, Rule, register

_SIZES_MM = {"A4": (210, 297)}
_SIZE_TOL_MM = 1.0
_MARGIN_TOL_MM = 0.5


def _mm(length) -> float:
    return (length or 0) / EMU_PER_MM


@register
class PageSizeRule(Rule):
    key = "page.size"
    fixable = True

    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        fmt = cfg.value.get("format", "A4")
        w, h = _SIZES_MM[fmt]
        portrait = cfg.value.get("orientation", "portrait") == "portrait"
        issues = []
        for i, s in enumerate(model.doc.sections, 1):
            sw, sh = _mm(s.page_width), _mm(s.page_height)
            is_portrait = sw <= sh
            short, long_ = sorted((sw, sh))
            ok = (
                abs(short - w) <= _SIZE_TOL_MM
                and abs(long_ - h) <= _SIZE_TOL_MM
                and is_portrait == portrait
            )
            if not ok:
                orient = "книжная" if portrait else "альбомная"
                actual_orient = "книжная" if is_portrait else "альбомная"
                exp = f"{fmt}, {orient}"
                act = f"{fmt_num(sw, 1)}×{fmt_num(sh, 1)} мм, {actual_orient}"
                issues.append(
                    Issue(
                        rule=self.key,
                        source=cfg.source,
                        severity=cfg.severity,
                        message=f"Формат страницы (раздел {i}): ожидается {exp}, найдено {act}",
                        expected=exp,
                        actual=act,
                        paragraph_index=None,
                        fixable=True,
                    )
                )
        return issues

    def fix(self, model: DocModel, cfg: RuleConfig) -> None:
        w, h = _SIZES_MM[cfg.value.get("format", "A4")]
        portrait = cfg.value.get("orientation", "portrait") == "portrait"
        if not portrait:
            w, h = h, w
        for s in model.doc.sections:
            s.page_width, s.page_height = Mm(w), Mm(h)
            s.orientation = WD_ORIENT.PORTRAIT if portrait else WD_ORIENT.LANDSCAPE


_SIDES = (
    ("top_mm", "top_margin", "верхнее"),
    ("bottom_mm", "bottom_margin", "нижнее"),
    ("left_mm", "left_margin", "левое"),
    ("right_mm", "right_margin", "правое"),
)


@register
class PageMarginsRule(Rule):
    key = "page.margins"
    fixable = True

    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        issues = []
        for i, s in enumerate(model.doc.sections, 1):
            for vkey, attr, name in _SIDES:
                exp = cfg.value[vkey]
                act = _mm(getattr(s, attr))
                if abs(act - exp) > _MARGIN_TOL_MM:
                    e, a = f"{fmt_num(exp, 1)} мм", f"{fmt_num(act, 1)} мм"
                    issues.append(
                        Issue(
                            rule=self.key,
                            source=cfg.source,
                            severity=cfg.severity,
                            message=f"Поле {name} (раздел {i}): ожидается {e}, найдено {a}",
                            expected=e,
                            actual=a,
                            paragraph_index=None,
                            fixable=True,
                        )
                    )
        return issues

    def fix(self, model: DocModel, cfg: RuleConfig) -> None:
        for s in model.doc.sections:
            for vkey, attr, _ in _SIDES:
                setattr(s, attr, Mm(cfg.value[vkey]))
