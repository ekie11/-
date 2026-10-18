import gostdoc_engine.rules  # noqa: F401
from gostdoc_engine.analyze import analyze
from gostdoc_engine.bibliography import Entry, check_entry, find_section, parse_entries
from tests.builders import build_docx

BOOK = "Иванов И. И. Название. — М. : Наука, 2020. — 100 с."


def section(blocks):
    return find_section(analyze(build_docx(blocks)))


def test_find_section_none():
    assert section([("p", "Текст.")]) is None


def test_find_section_bounds_and_alt_title():
    for title in ("СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", "Список литературы", "БИБЛИОГРАФИЧЕСКИЙ СПИСОК",
                  "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ"):
        sec = section([("p", "До."), ("structural", title), ("source", f"1. {BOOK}"),
                       ("source", f"2. {BOOK}"), ("structural", "ПРИЛОЖЕНИЕ А"), ("p", "После.")])
        assert [p.text for p in sec] == [f"1. {BOOK}", f"2. {BOOK}"]


def test_parse_three_entries_one_multiparagraph():
    sec = section([("structural", "СПИСОК ЛИТЕРАТУРЫ"), ("source", f"1. {BOOK}"),
                   ("source", "2. Петров П. П. Книга. —"), ("source", "СПб. : Питер, 2019. — 5 с."),
                   ("source", f"3) {BOOK}")])
    entries = parse_entries(sec)
    assert [e.number for e in entries] == [1, 2, 3]
    assert "СПб. : Питер" in entries[1].text and "Петров" in entries[1].text


def test_check_entry_ok_and_problems():
    assert check_entry(Entry(1, BOOK, 0)) == []
    assert check_entry(Entry(1, "Иванов И. И. Название. — М. : Наука. — 100 с.", 0)) == [
        "Источник 1: нет года издания"]
    msgs = check_entry(Entry(2, "Сайт. — URL: http://x.ru, 2020. — Текст : электронный.", 0))
    assert "Источник 2: у электронного ресурса нет даты обращения" in msgs
    msgs = check_entry(Entry(3, "Иванов И. Статья 2020", 0))
    assert any("нет выходных данных" in m for m in msgs)
    assert check_entry(Entry(4, "Иванов И. Статья // Журнал. — 2020. — № 1.", 0)) == []
