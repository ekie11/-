import pytest

from gostdoc_engine.analyze import analyze, classify_text
from gostdoc_engine.model import Role
from tests.builders import build_docx

BLOCKS = [
    ("structural", "ВВЕДЕНИЕ"),
    ("p", "Текст введения."),
    ("h1", "1 Обзор"),
    ("h2", "1.1 Рынок"),
    ("p", "Основной текст."),
    ("figure", "alt"),
    ("figure_caption", "Рисунок 1 — Схема"),
    ("table_caption", "Таблица 1 — Данные"),
    ("table", "а|б;в|г"),
    ("empty", ""),
    ("structural", "ЗАКЛЮЧЕНИЕ"),
]


def roles(model):
    return [(p.text, p.role) for p in model.paragraphs]


@pytest.mark.parametrize("styles", [True, False])
def test_roles(styles):
    m = analyze(build_docx(BLOCKS, use_heading_styles=styles))
    r = dict(roles(m))
    assert r["ВВЕДЕНИЕ"] == Role.STRUCTURAL
    assert r["ЗАКЛЮЧЕНИЕ"] == Role.STRUCTURAL
    assert r["1 Обзор"] == Role.HEADING_1
    assert r["1.1 Рынок"] == Role.HEADING_2
    assert r["Основной текст."] == Role.BODY
    assert r["Рисунок 1 — Схема"] == Role.FIGURE_CAPTION
    assert r["Таблица 1 — Данные"] == Role.TABLE_CAPTION
    assert r[""] == Role.EMPTY or Role.EMPTY in [p.role for p in m.paragraphs]
    assert [p.index for p in m.paragraphs] == list(range(len(m.paragraphs)))


def test_roles_with_styles():
    test_roles(True)


def test_roles_without_heading_styles():
    test_roles(False)


def test_numbered_body_sentence_not_heading():
    text = "1 января компания открыла офис в Москве и наняла сорок сотрудников."
    m = analyze(build_docx([("p", text)]))
    assert m.paragraphs[0].role == Role.BODY


def test_table_cells_are_in_table():
    m = analyze(build_docx(BLOCKS))
    cells = m.by_role(Role.IN_TABLE)
    assert [c.text for c in cells] == ["а", "б", "в", "г"]
    idx = [p.index for p in m.paragraphs]
    assert m.paragraphs[idx[cells[0].index] - 1].role == Role.TABLE_CAPTION


def test_toc_and_title_page():
    m = analyze(
        build_docx(
            [
                ("p", "Министерство"),
                ("structural", "СОДЕРЖАНИЕ"),
                ("p", "1 Обзор ..... 3"),
                ("structural", "ВВЕДЕНИЕ"),
                ("p", "Текст"),
            ]
        )
    )
    assert [p.role for p in m.paragraphs] == [
        Role.TITLE_PAGE,
        Role.STRUCTURAL,
        Role.TOC,
        Role.STRUCTURAL,
        Role.BODY,
    ]


def test_classify_text():
    assert classify_text("ПРИЛОЖЕНИЕ А", False) == Role.STRUCTURAL
    assert classify_text("Рис. 2 — x", False) == Role.FIGURE_CAPTION
    assert classify_text("1.2.3 Пункт", False) == Role.HEADING_3
    assert classify_text("Просто текст", True) is None
