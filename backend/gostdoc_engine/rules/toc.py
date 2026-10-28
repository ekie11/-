"""Правило оглавления: автоматическое поле TOC со ссылками после «СОДЕРЖАНИЕ»."""

from .. import toc
from ..model import DocModel, Role
from ..profile import RuleConfig
from .base import Issue, Rule, register

MANUAL = "Содержание набрано вручную — будет заменено автоматическим оглавлением"
MISMATCH = (
    "Содержание набрано вручную и не совпадает с заголовками — автоматическое "
    "оглавление не вставлено, проверьте содержание вручную"
)
MISSING = "Нет автоматического оглавления"


@register
class TocRule(Rule):
    key = "toc"
    fixable = True
    order = 100  # после правил заголовков

    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        heading = toc.toc_heading(model)
        if heading is None or toc.has_toc_field(model.doc) or not toc.has_entries(model):
            return []
        if toc.manual_toc_problem(model):
            return [
                Issue(
                    rule=self.key,
                    source=cfg.source,
                    severity=cfg.severity,
                    message=MISMATCH,
                    expected="автоматическое оглавление",
                    actual="вручную",
                    paragraph_index=heading.index,
                    fixable=False,
                )
            ]
        manual = any(p.role == Role.TOC and p.text.strip() for p in model.paragraphs)
        message = MANUAL if manual else MISSING
        return [
            Issue(
                rule=self.key,
                source=cfg.source,
                severity=cfg.severity,
                message=message,
                expected="автоматическое оглавление",
                actual="вручную" if manual else "нет",
                paragraph_index=heading.index,
                fixable=True,
            )
        ]

    def fix(self, model: DocModel, cfg: RuleConfig) -> None:
        if toc.manual_toc_problem(model):
            return
        toc.apply_heading_styles(model)
        toc.build_toc(model)
