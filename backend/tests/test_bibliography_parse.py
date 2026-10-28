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
    for title in (
        "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ",
        "Список литературы",
        "БИБЛИОГРАФИЧЕСКИЙ СПИСОК",
        "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
    ):
        sec = section(
            [
                ("p", "До."),
                ("structural", title),
                ("source", f"1. {BOOK}"),
                ("source", f"2. {BOOK}"),
                ("structural", "ПРИЛОЖЕНИЕ А"),
                ("p", "После."),
            ]
        )
        assert [p.text for p in sec] == [f"1. {BOOK}", f"2. {BOOK}"]


def test_parse_three_entries_one_multiparagraph():
    sec = section(
        [
            ("structural", "СПИСОК ЛИТЕРАТУРЫ"),
            ("source", f"1. {BOOK}"),
            ("source", "2. Петров П. П. Книга. —"),
            ("source", "СПб. : Питер, 2019. — 5 с."),
            ("source", f"3) {BOOK}"),
        ]
    )
    entries = parse_entries(sec)
    assert [e.number for e in entries] == [1, 2, 3]
    assert "СПб. : Питер" in entries[1].text and "Петров" in entries[1].text


def test_check_entry_ok_and_problems():
    assert check_entry(Entry(1, BOOK, 0)) == []
    assert check_entry(Entry(1, "Иванов И. И. Название. — М. : Наука. — 100 с.", 0)) == [
        "Источник 1: нет года издания"
    ]
    msgs = check_entry(Entry(2, "Сайт. — URL: http://x.ru, 2020. — Текст : электронный.", 0))
    assert "Источник 2: у электронного ресурса нет даты обращения" in msgs
    msgs = check_entry(Entry(3, "Иванов И. Статья 2020", 0))
    assert any("нет выходных данных" in m for m in msgs)
    assert check_entry(Entry(4, "Иванов И. Статья // Журнал. — 2020. — № 1.", 0)) == []


def test_toc_line_does_not_hide_real_section():
    sec = section(
        [
            ("structural", "СОДЕРЖАНИЕ"),
            ("p", "Список литературы"),
            ("structural", "ВВЕДЕНИЕ"),
            ("p", "Текст."),
            ("structural", "СПИСОК ЛИТЕРАТУРЫ"),
            ("source", f"1. {BOOK}"),
            ("source", f"2. {BOOK}"),
        ]
    )
    assert [e.number for e in parse_entries(sec)] == [1, 2]


def test_gap_after_paren_and_not_greater_is_continuation():
    sec = section(
        [
            ("structural", "СПИСОК ЛИТЕРАТУРЫ"),
            ("source", f"1. {BOOK}"),
            ("source", "2. Сайт. — URL: http://x.ru (дата обращения: 01.01.2020)"),
            ("source", "4. Книга. — М. : Наука, 2020."),
        ]
    )
    assert [e.number for e in parse_entries(sec)] == [1, 2, 4]
    sec = section(
        [
            ("structural", "СПИСОК ЛИТЕРАТУРЫ"),
            ("source", f"5. {BOOK}"),
            ("source", "1. продолжение"),
        ]
    )
    assert len(parse_entries(sec)) == 1


def test_heading_after_list_stays_heading():
    from gostdoc_engine.model import Role

    m = analyze(
        build_docx(
            [
                ("structural", "СПИСОК ЛИТЕРАТУРЫ"),
                ("source", "1. Иванов И. И. Название"),
                ("h1", "5 Приложение данных"),
            ]
        )
    )
    assert m.paragraphs[2].role == Role.HEADING_1


def test_continuation_with_number_like_start():
    sec = section(
        [
            ("structural", "СПИСОК ЛИТЕРАТУРЫ"),
            ("source", "1. Иванов И. Книга. — М. : Наука,"),
            ("source", "1999. — 300 с."),
            ("source", f"2. {BOOK}"),
        ]
    )
    entries = parse_entries(sec)
    assert [e.number for e in entries] == [1, 2]
    assert "1999. — 300 с." in entries[0].text


def test_real_gap_still_new_entry_numbers():
    sec = section(
        [
            ("structural", "СПИСОК ЛИТЕРАТУРЫ"),
            ("source", f"1. {BOOK}"),
            ("source", f"2. {BOOK}"),
            ("source", f"4. {BOOK}"),
        ]
    )
    assert [e.number for e in parse_entries(sec)] == [1, 2, 4]


def test_entries_not_headings():
    from gostdoc_engine.model import Role

    m = analyze(
        build_docx(
            [
                ("structural", "СПИСОК ЛИТЕРАТУРЫ"),
                ("source", "1. Иванов И. И. Название"),
                ("source", "2. Петров П. П. Другое"),
                ("structural", "ПРИЛОЖЕНИЕ А"),
            ]
        )
    )
    assert [p.role for p in m.paragraphs[1:3]] == [Role.LIST_ITEM] * 2
