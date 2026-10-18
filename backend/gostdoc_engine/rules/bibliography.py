"""Правило списка источников."""

import re

from ..bibliography import check_entry, find_section, parse_entries
from ..model import DocModel, Role
from ..profile import RuleConfig
from .base import Issue, Rule, register

_CITATION = re.compile(r"\[\d+")


@register
class BibliographyRule(Rule):
    key = "bibliography"
    fixable = False

    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        def issue(msg, idx, severity=None):
            return Issue(rule=self.key, source=cfg.source, severity=severity or cfg.severity,
                         message=msg, expected="", actual="", paragraph_index=idx, fixable=False)

        section = find_section(model)
        if section is None:
            if any(_CITATION.search(p.text) for p in model.paragraphs
                   if p.role not in (Role.IN_TABLE, Role.EMPTY)):
                return [issue("Не найден раздел «Список использованных источников»", None,
                              "recommendation")]
            return []
        issues = []
        prev = 0
        for pos, entry in enumerate(parse_entries(section), start=1):
            if entry.number is None:
                entry.number = pos
            if entry.number != prev + 1:
                issues.append(issue(
                    f"Нумерация источников нарушена: после {prev} идёт {entry.number}",
                    entry.paragraph_index))
            prev = entry.number
            for msg in check_entry(entry):
                sev = "recommendation" if "вместо «[Электронный ресурс]»" in msg else None
                issues.append(issue(msg, entry.paragraph_index, sev))
        return issues
