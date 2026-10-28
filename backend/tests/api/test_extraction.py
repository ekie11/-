from gostdoc_api import extraction
from gostdoc_api.config import Settings
from gostdoc_api.extraction import build_messages, run_extraction, validate

TEXT = (
    "[стр. 1]\nОбщие требования. Поля: левое — «30 мм», правое — 10 мм.\n"
    "Текст печатается шрифтом Times New Roman, интервал\nполуторный.\n"
    "[стр. 2]\nКегль 14 пт, отступ абзаца 1,25 см."
)


def _f(rule, path, value, quote):
    return {"rule": rule, "path": path, "value": value, "quote": quote}


def _val(items, text=TEXT):
    return validate({"found": items, "unsupported": []}, text)


def test_valid_with_page():
    r = _val([_f("page.margins", "left_mm", 30, "левое — «30 мм»")])
    assert r["rejected_count"] == 0
    item = r["found"][0]
    assert item["value"] == 30.0 and item["page"] == 1
    r = _val([_f("body.font_size", "target_pt", 14, "Кегль 14 пт")])
    assert r["found"][0]["page"] == 2


def test_rejects_counted():
    items = [
        _f("page.margins", "left_mm", 30, "выдуманная цитата про поля"),
        _f("no.such", "x", 1, "левое — «30 мм»"),
        _f("page.size", "format", "A4", "левое — «30 мм»"),
        _f("page.margins", "top_mm", 999, "правое — 10 мм"),
        _f("page.size", "orientation", "diagonal", "правое — 10 мм"),
    ]
    r = _val(items)
    assert r["found"] == [] and r["rejected_count"] == 5


def test_duplicate_keeps_first():
    r = _val(
        [
            _f("page.margins", "left_mm", 30, "левое — «30 мм»"),
            _f("page.margins", "left_mm", 10, "правое — 10 мм"),
        ]
    )
    assert [i["value"] for i in r["found"]] == [30.0]
    assert r["rejected_count"] == 1


def test_quote_variants_found():
    # другие кавычки/тире, перенос строки, ё
    r = _val(
        [
            _f("page.margins", "left_mm", 30, 'левое - "30 мм"'),
            _f("page.margins", "right_mm", 10, "ПРАВОЕ — 10 мм"),
            _f("body.font_name", "name", "Times New Roman", "ШРИФТОМ TIMES NEW ROMAN"),
        ]
    )
    assert r["rejected_count"] == 0 and len(r["found"]) == 3


def test_short_quote_rejected():
    assert _val([_f("page.margins", "left_mm", 30, "30 мм")])["rejected_count"] == 1


def test_coercion():
    r = _val(
        [
            _f("body.font_size", "target_pt", "14 пт", "Кегль 14 пт"),
            _f("body.first_line_indent", "cm", "1,25", "отступ абзаца 1,25 см"),
            _f("body.line_spacing", "multiple", "полуторный", "интервал полуторный"),
        ]
    )
    assert [i["value"] for i in r["found"]] == [14.0, 1.25]
    assert r["rejected_count"] == 1


def test_bool_and_text():
    t = "Заголовки жирным. Шрифт Arial."
    r = validate(
        {
            "found": [
                _f("headings.section", "bold", "да", "Заголовки жирным"),
                _f("headings.structural", "bold", "maybe", "Заголовки жирным"),
                _f("body.font_name", "name", "x" * 201, "Шрифт Arial."),
            ]
        },
        t,
    )
    assert r["found"][0]["value"] is True
    assert r["found"][0]["page"] is None
    assert r["rejected_count"] == 2


def test_unsupported():
    r = validate(
        {
            "found": [],
            "unsupported": [
                {"text": "Нумерация приложений", "quote": "отступ абзаца 1,25 см"},
                {"text": "Выдумка", "quote": "этого нет в тексте вообще"},
            ],
        },
        TEXT,
    )
    assert len(r["unsupported"]) == 1 and r["unsupported"][0]["page"] == 2
    assert r["rejected_count"] == 1


def test_garbage_input():
    assert validate({"found": "x", "unsupported": None}, TEXT)["found"] == []
    assert validate({"found": ["s", {"rule": 1}]}, TEXT)["rejected_count"] == 2


def test_build_messages():
    system, user = build_messages("текст")
    assert user == "<<<МЕТОДИЧКА\nтекст\nМЕТОДИЧКА>>>"
    assert "page.margins" in system and "left_mm" in system
    assert "page.size" in system and "orientation" in system
    assert "format" not in system.split("page.size", 1)[1].split("\n")[0]
    assert "toc" not in system.replace("unsupported", "")
    assert "unsupported" in system


def test_run_extraction(monkeypatch):
    seen = {}

    def fake(system, user, *, settings, transport=None):
        seen["user"] = user
        return {"found": [_f("page.margins", "left_mm", 30, "левое — «30 мм»")]}

    monkeypatch.setattr(extraction, "chat_json", fake)
    s = Settings(database_url="sqlite://", redis_url="r", storage_dir="/tmp/x")
    r = run_extraction(TEXT, s)
    assert r["found"][0]["page"] == 1 and "МЕТОДИЧКА>>>" in seen["user"]


def test_unsupported_text_capped():
    q = "Кегль 14 пт"
    r = validate({"found": [], "unsupported": [{"text": "я" * 500, "quote": q}]}, TEXT)
    assert len(r["unsupported"][0]["text"]) == 300


def test_number_in_quote_comma_and_dot():
    t = "Отступ абзаца 1,25 см, кегль 14 пт, интервал 1.5."
    r = validate(
        {
            "found": [
                _f("body.first_line_indent", "cm", 1.25, "отступ абзаца 1,25 см"),
                _f("body.font_size", "target_pt", 14.0, "кегль 14 пт"),
                _f("body.line_spacing", "multiple", 1.5, "интервал 1,5 или 1.5 — интервал 1.5."),
            ],
            "unsupported": [],
        },
        t,
    )
    assert r["rejected_count"] == 1  # третья цитата не найдена в тексте
    t2 = "Отступ абзаца 1.25 см."
    r = validate(
        {
            "found": [_f("body.first_line_indent", "cm", 1.25, "отступ абзаца 1.25 см")],
            "unsupported": [],
        },
        t2,
    )
    assert r["rejected_count"] == 0 and len(r["found"]) == 1


def test_number_absent_from_quote_rejected():
    r = _val([_f("body.line_spacing", "multiple", 1.5, "интервал полуторный")])
    assert r["found"] == [] and r["rejected_count"] == 1


def test_number_not_matched_inside_bigger_number():
    t = "Размер 140 пт и 21,25 мм, 14,5 пт."
    for val, quote in ((14, "Размер 140 пт"), (1.25, "и 21,25 мм"), (14, "14,5 пт")):
        r = validate(
            {"found": [_f("body.font_size", "target_pt", val, quote)], "unsupported": []}, t
        )
        assert r["found"] == [] and r["rejected_count"] == 1, quote


def test_unsupported_dedup_against_found():
    t = "Нумерация страниц по центру вверху страницы. Шрифт 14 пт обязателен."
    r = validate(
        {
            "found": [_f("body.font_size", "target_pt", 14, "Шрифт 14 пт обязателен")],
            "unsupported": [
                {"text": "дубль", "quote": "ШРИФТ 14 пт обязателен"},
                {"text": "часть", "quote": "Шрифт 14 пт"},
                {"text": "шире", "quote": "Шрифт 14 пт обязателен."},
                {"text": "своё", "quote": "Нумерация страниц по центру вверху"},
            ],
        },
        t,
    )
    assert [u["text"] for u in r["unsupported"]] == ["своё"]


def test_prompt_rules():
    system, _ = build_messages("текст")
    assert "явно" in system and 'либо в "found", либо в "unsupported"' in system


def test_zero_in_words_and_trailing_zeros():
    t = "Таблица: без абзацного отступа. Интервал 1,50. Кегль 2,0 см, 14,0 пт, 14,05 и 140."
    ok = [
        _f("captions.table", "first_line_indent_cm", 0, "без абзацного отступа"),
        _f("body.line_spacing", "multiple", 1.5, "Интервал 1,50"),
        _f("body.first_line_indent", "cm", 2.0, "Кегль 2,0 см"),
        _f("body.font_size", "target_pt", 14, "см, 14,0 пт"),
    ]
    r = validate({"found": ok, "unsupported": []}, t)
    assert r["rejected_count"] == 0 and len(r["found"]) == 4
    for val, q in ((14, "14,05 и 140"), (0, "Интервал 1,50")):
        r = validate({"found": [_f("body.font_size", "target_pt", val, q)], "unsupported": []}, t)
        assert r["found"] == []


SEL = (
    "Страницы книжной ориентации. Заголовок размещают посередине строки. "
    "Текст выравнивают слева. Номер по центру вверху страницы. "
    "Шрифт Times New Roman. Подпись: Рисунок 1 — Название."
)


def _sel(rule, path, value, quote):
    return validate({"found": [_f(rule, path, value, quote)], "unsupported": []}, SEL)


def test_pattern_accepted_and_rejected():
    q = "Рисунок 1 — Название"
    ok = _sel("captions.figure", "pattern", "Рисунок {n} — {title}", q)
    assert len(ok["found"]) == 1
    for bad in (
        "Таблица X.Y − Название",
        "Рисунок {number} – {name}",
        "Рисунок {n}",
        "Рисунок {title}",
        "Рисунок {n} — {title} {x}",
    ):
        r = _sel("captions.figure", "pattern", bad, q)
        assert r["found"] == [] and r["rejected_count"] == 1, bad


def test_pattern_prompt_mentions_placeholders():
    system, _ = build_messages("x")
    assert "{n}" in system and "{title}" in system


def test_select_evidence():
    r = _sel("page.size", "orientation", "portrait", "Шрифт Times New Roman")
    assert r["found"] == [] and r["rejected_count"] == 1
    assert _sel("page.size", "orientation", "portrait", "Страницы книжной ориентации")["found"]
    assert _sel("headings.section", "align", "center", "посередине строки")["found"]
    assert _sel("body.alignment", "align", "left", "выравнивают слева")["found"]
    assert _sel("page_numbers", "position", "top_center", "по центру вверху")["found"]
    assert _sel("body.alignment", "align", "right", "выравнивают слева")["found"] == []
