"""Тесты раннера правил и реестра."""

from typing import ClassVar

import pytest

from gostdoc_engine.model import DocModel
from gostdoc_engine.profile import KNOWN_RULE_KEYS, Profile, RuleConfig
from gostdoc_engine.rules import base
from gostdoc_engine.rules.base import REGISTRY, Issue, Rule, register
from gostdoc_engine.runner import run_check, run_fix

KEY_A = "page.size"
KEY_B = "body.font_name"
KEY_C = "body.font_size"

assert {KEY_A, KEY_B, KEY_C} <= KNOWN_RULE_KEYS


@pytest.fixture(autouse=True)
def registry_snapshot():
    saved = dict(REGISTRY)
    REGISTRY.clear()  # изоляция от реальных правил, зарегистрированных при импорте
    yield REGISTRY
    REGISTRY.clear()
    REGISTRY.update(saved)


def _model() -> DocModel:
    return DocModel(doc=None, paragraphs=[])


def _profile(**rules: RuleConfig) -> Profile:
    return Profile(id="test", name="Тест", base=None, readonly=False, rules=rules)


def _cfg(enabled: bool = True) -> RuleConfig:
    return RuleConfig(value={}, severity="error", enabled=enabled, source="тест")


def _issue(rule: str, fixable: bool = False) -> Issue:
    return Issue(
        rule=rule,
        source="тест",
        severity="error",
        message="сообщение",
        expected="ожидание",
        actual="факт",
        paragraph_index=None,
        fixable=fixable,
    )


def test_registry_snapshot_restores_global_registry():
    assert REGISTRY is base.REGISTRY
    assert KEY_A not in REGISTRY


def test_register_adds_rule_to_registry_and_returns_class():
    @register
    class _Rule(Rule):
        key: ClassVar[str] = KEY_A
        fixable: ClassVar[bool] = False

        def check(self, model, cfg):
            return []

    assert REGISTRY[KEY_A] is _Rule


def test_disabled_rule_is_not_called():
    calls: list[str] = []

    @register
    class _Rule(Rule):
        key: ClassVar[str] = KEY_A
        fixable: ClassVar[bool] = True

        def check(self, model, cfg):
            calls.append("check")
            return [_issue(KEY_A)]

        def fix(self, model, cfg):
            calls.append("fix")

    profile = _profile(**{KEY_A: _cfg(enabled=False)})

    result = run_check(_model(), profile)
    run_fix(_model(), profile)

    assert calls == []
    assert result.issues == []
    assert result.failed_rules == []


def test_raising_rule_goes_to_failed_rules_and_next_rule_runs():
    @register
    class _Broken(Rule):
        key: ClassVar[str] = KEY_B
        fixable: ClassVar[bool] = False

        def check(self, model, cfg):
            raise RuntimeError("сбой")

    @register
    class _Ok(Rule):
        key: ClassVar[str] = KEY_C
        fixable: ClassVar[bool] = False

        def check(self, model, cfg):
            return [_issue(KEY_C)]

    profile = _profile(**{KEY_B: _cfg(), KEY_C: _cfg()})

    result = run_check(_model(), profile)

    assert result.failed_rules == [KEY_B]
    assert [i.rule for i in result.issues] == [KEY_C]


def test_run_fix_does_not_call_fix_of_non_fixable_rule():
    calls: list[str] = []

    @register
    class _Rule(Rule):
        key: ClassVar[str] = KEY_A
        fixable: ClassVar[bool] = False

        def check(self, model, cfg):
            return []

        def fix(self, model, cfg):
            calls.append("fix")

    run_fix(_model(), _profile(**{KEY_A: _cfg()}))

    assert calls == []


def test_run_fix_calls_fix_of_fixable_rule():
    calls: list[str] = []

    @register
    class _Rule(Rule):
        key: ClassVar[str] = KEY_A
        fixable: ClassVar[bool] = True

        def check(self, model, cfg):
            return []

        def fix(self, model, cfg):
            calls.append("fix")

    run_fix(_model(), _profile(**{KEY_A: _cfg()}))

    assert calls == ["fix"]


def test_run_fix_exception_is_logged_and_next_rule_runs(caplog):
    calls: list[str] = []

    @register
    class _Broken(Rule):
        key: ClassVar[str] = KEY_B
        fixable: ClassVar[bool] = True

        def check(self, model, cfg):
            return []

        def fix(self, model, cfg):
            raise RuntimeError("сбой")

    @register
    class _Ok(Rule):
        key: ClassVar[str] = KEY_C
        fixable: ClassVar[bool] = True

        def check(self, model, cfg):
            return []

        def fix(self, model, cfg):
            calls.append("fix")

    with caplog.at_level("ERROR"):
        run_fix(_model(), _profile(**{KEY_B: _cfg(), KEY_C: _cfg()}))

    assert calls == ["fix"]
    assert any(KEY_B in r.getMessage() or KEY_B in str(r.exc_info) for r in caplog.records)


def test_profile_key_without_registered_rule_is_skipped():
    result = run_check(_model(), _profile(**{KEY_A: _cfg()}))

    assert result.issues == []
    assert result.failed_rules == []
    run_fix(_model(), _profile(**{KEY_A: _cfg()}))
