"""Правило списка источников."""

import re

from ..bibliography import (
    check_entry,
    find_citations,
    find_section,
    fix_paragraph_typography,
    is_unnumbered,
    parse_entries,
)
from ..model import DocModel, Role
from ..profile import RuleConfig
from .base import Issue, Rule, register

_CITATION = re.compile(r"\[\d+")


@register
class BibliographyRule(Rule):
    key = "bibliography"
    fixable = True

    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        def issue(msg, idx, severity=None):
            return Issue(
                rule=self.key,
                source=cfg.source,
                severity=severity or cfg.severity,
                message=msg,
                expected="",
                actual="",
                paragraph_index=idx,
                fixable=False,
            )

        section = find_section(model)
        if section is None:
            if any(
                _CITATION.search(p.text)
                for p in model.paragraphs
                if p.role not in (Role.IN_TABLE, Role.EMPTY)
            ):
                return [
                    issue(
                        "Не найден раздел «Список использованных источников»",
                        None,
                        "recommendation",
                    )
                ]
            return []
        issues = []
        prev = 0
        entries = parse_entries(section)
        if is_unnumbered(section):
            issues.append(
                issue(
                    "Источники в списке не пронумерованы",
                    entries[0].paragraph_index,
                    "recommendation",
                )
            )
        for pos, e in enumerate(entries, start=1):
            if e.number is None:
                e.number = pos
        for entry in entries:
            if entry.number != prev + 1:
                issues.append(
                    issue(
                        f"Источник {entry.number}: нарушена нумерация, ожидался номер {prev + 1}",
                        entry.paragraph_index,
                    )
                )
            prev = entry.number
            for msg in check_entry(entry):
                rec = "вместо «[Электронный ресурс]»" in msg or "вместо дефиса" in msg
                sev = "recommendation" if rec else None
                issues.append(issue(msg, entry.paragraph_index, sev))
        issues.extend(self._citation_issues(model, cfg, entries, issue))
        return issues

    @staticmethod
    def _citation_issues(model, cfg, entries, issue):
        out = []
        numbers = {e.number for e in entries}
        cited: set[int] = set()
        first: list[int] = []
        for idx, nums in find_citations(model):
            seen = set()
            for n in nums:
                cited.add(n)
                if n not in first:
                    first.append(n)
                if n not in numbers and n not in seen:
                    seen.add(n)
                    out.append(issue(f"Ссылка [{n}] указывает на несуществующий источник", idx))
        for e in entries:
            if e.number not in cited:
                out.append(
                    issue(
                        f"На источник {e.number} нет ссылки в тексте",
                        e.paragraph_index,
                        "recommendation",
                    )
                )
        known = [n for n in first if n in numbers]
        if cfg.value.get("order") == "mention" and known != sorted(known):
            out.append(issue("Источники пронумерованы не в порядке упоминания", None))
        return out

    def fix(self, model: DocModel, cfg: RuleConfig) -> None:
        for p in find_section(model) or []:
            fix_paragraph_typography(p.para)
