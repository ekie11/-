import gostdoc_engine.rules  # noqa: F401
from gostdoc_engine.analyze import analyze
from gostdoc_engine.profile import builtin_profile
from gostdoc_engine.rules.base import REGISTRY
from tests.builders import build_docx

KEY = "bibliography"
BOOK = "Иванов И. И. Название. — М. : Наука, 2020. — 100 с."


def check(blocks, pid="gost-7.32-2017"):
    cfg = builtin_profile(pid).rules[KEY]
    return REGISTRY[KEY]().check(analyze(build_docx(blocks)), cfg)


def test_no_section_no_refs():
    assert check([("p", "Просто текст.")]) == []


def test_no_section_with_ref():
    issues = check([("p", "Как показано в [1].")])
    assert len(issues) == 1 and issues[0].severity == "recommendation"
    assert issues[0].message == "Не найден раздел «Список использованных источников»"


def test_clean():
    assert check([("structural", "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"),
                  ("source", f"1. {BOOK}"), ("source", f"2. {BOOK}")]) == []


def test_numbering_and_entry_problems():
    issues = check([("structural", "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"),
                    ("source", f"1. {BOOK}"),
                    ("source", "2. Иванов И. Статья // Журнал. — 2020."),
                    ("source", "4. Книга без года. — М. : Наука."),
                    ("source", "5. Сайт. — URL: http://x.ru, 2020. [Электронный ресурс]")])
    msgs = [i.message for i in issues]
    assert "Нумерация источников нарушена: после 2 идёт 4" in msgs
    assert "Источник 4: нет года издания" in msgs
    assert "Источник 5: у электронного ресурса нет даты обращения" in msgs
    assert "Источник 5: используйте «Текст : электронный» вместо «[Электронный ресурс]»" in msgs
    rec = [i for i in issues if i.severity == "recommendation"]
    assert len(rec) == 1
    assert all(not i.fixable for i in issues)
