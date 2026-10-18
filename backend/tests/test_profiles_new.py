"""Профили ГОСТ 2.105-2019 и ЕСПД."""

import pytest

from gostdoc_engine.analyze import analyze
from gostdoc_engine.profile import KNOWN_RULE_KEYS, builtin_profile, list_builtin_profiles
from gostdoc_engine.runner import run_check
from tests.builders import build_docx

PIDS = ["gost-2.105-2019", "espd-19.106-78"]
BLOCKS = [
    ("structural", "ВВЕДЕНИЕ"),
    ("p", "Текст работы."),
    ("h1", "1 Анализ"),
    ("p", "Основной текст раздела."),
    ("figure", "Схема"),
    ("figure_caption", "Рисунок 1 – Схема"),
    ("table_caption", "Таблица 1 – Данные"),
    ("table", "a|b;c|d"),
]
KW = dict(  # noqa: C408
    margins_mm=(20, 20, 20, 10), font="Times New Roman", size_pt=14,
    line_spacing=1.5, indent_cm=1.25, align="justify",
)


def _check(pid, **over):
    doc = build_docx(BLOCKS, **{**KW, **over})
    return run_check(analyze(doc), builtin_profile(pid))


@pytest.mark.parametrize("pid", PIDS)
def test_loads_and_valid(pid):
    p = builtin_profile(pid)
    assert p.id == pid and p.readonly is True and p.base is None
    assert set(p.rules) == KNOWN_RULE_KEYS
    assert p.rules["page.margins"].value["left_mm"] == 20
    assert all(r.source for r in p.rules.values())


@pytest.mark.parametrize("pid", PIDS)
def test_listed(pid):
    assert pid in {p.id for p in list_builtin_profiles()}


@pytest.mark.parametrize("pid", PIDS)
def test_compliant_document_has_no_errors(pid):
    res = _check(pid)
    errors = [i for i in res.issues if i.severity == "error"]
    assert errors == [], errors


@pytest.mark.parametrize("pid", PIDS)
def test_margin_violation_single_issue_with_source(pid):
    res = _check(pid, margins_mm=(10, 20, 20, 10))
    issues = [i for i in res.issues if i.rule == "page.margins"]
    assert len(issues) == 1
    assert issues[0].source == builtin_profile(pid).rules["page.margins"].source


@pytest.mark.parametrize("pid", PIDS)
def test_captions_use_en_dash(pid):
    p = builtin_profile(pid)
    assert "–" in p.rules["captions.figure"].value["pattern"]
    assert "–" in p.rules["captions.table"].value["pattern"]
