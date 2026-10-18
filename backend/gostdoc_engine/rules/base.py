"""Базовый класс правила, реестр и модель замечания."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from ..model import DocModel
from ..profile import RuleConfig


@dataclass
class Issue:
    rule: str
    source: str
    severity: str
    message: str
    expected: str
    actual: str
    paragraph_index: int | None
    fixable: bool


class Rule(ABC):
    key: ClassVar[str]
    fixable: ClassVar[bool]
    order: ClassVar[int] = 0  # порядок исправления: меньшие раньше

    @abstractmethod
    def check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]:
        """Вернуть замечания по документу."""

    def fix(self, model: DocModel, cfg: RuleConfig) -> None:
        raise NotImplementedError(f"Правило {self.key} не умеет исправлять документ")


REGISTRY: dict[str, type[Rule]] = {}


def register(rule_cls: type[Rule]) -> type[Rule]:
    REGISTRY[rule_cls.key] = rule_cls
    return rule_cls
