"""Запуск правил профиля над моделью документа."""

import logging
from dataclasses import dataclass, field

from .model import DocModel
from .profile import Profile
from .rules.base import REGISTRY, Issue

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    issues: list[Issue] = field(default_factory=list)
    failed_rules: list[str] = field(default_factory=list)


def run_check(model: DocModel, profile: Profile) -> RunResult:
    result = RunResult()
    for key, cfg in profile.rules.items():
        rule_cls = REGISTRY.get(key)
        if not cfg.enabled or rule_cls is None:
            continue
        try:
            result.issues.extend(rule_cls().check(model, cfg))
        except Exception:
            logger.exception("Правило %s завершилось с ошибкой", key)
            result.failed_rules.append(key)
    return result


def run_fix(model: DocModel, profile: Profile) -> list[str]:
    """Применить исправления; вернуть ключи правил, чьё исправление упало."""
    failed: list[str] = []
    ordered = sorted(
        profile.rules.items(), key=lambda kv: getattr(REGISTRY.get(kv[0]), "order", 0)
    )
    for key, cfg in ordered:
        rule_cls = REGISTRY.get(key)
        if not cfg.enabled or rule_cls is None or not rule_cls.fixable:
            continue
        try:
            rule_cls().fix(model, cfg)
        except Exception:
            logger.exception("Исправление правила %s завершилось с ошибкой", key)
            failed.append(key)
    return failed
