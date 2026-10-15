# Этап 1: движок, профиль ГОСТ 7.32-2017, базовые правила — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Python-пакет `gostdoc_engine` с CLI, который принимает DOCX или текст, применяет профиль требований в режиме «Проверить» или «Оформить» и выдаёт DOCX с комментариями Word и JSON-отчёт.

**Architecture:** Конвейер `import → analyze → rules (check/fix) → comments → output`. Профиль — JSON, валидируемый Pydantic. Каждое правило — класс с `check`/`fix`, правила регистрируются по ключу профиля. API, БД, фронтенд и PDF — следующие этапы, здесь их нет.

**Tech Stack:** Python 3.12, python-docx ≥ 1.2 (нативные комментарии Word), lxml, Pydantic 2, pytest, ruff.

**Spec:** `docs/specs/2026-10-15-gost-formatter-design.md`

## Global Constraints

- Код бэкенда — в `backend/`, пакет `backend/gostdoc_engine/`, тесты — `backend/tests/`.
- Профили — `backend/profiles/*.json`; id ГОСТ-профиля 7.32: `gost-7.32-2017`.
- Правило профиля: `value`, `severity` (`error` | `recommendation`), `enabled`, `source`.
- Движок меняет только оформление; текст меняется только типографикой (кавычки, тире, пробелы).
- Входной файл: только DOCX, не больше 20 МБ; иначе понятная ошибка на русском.
- Исключение внутри одного правила не роняет обработку: правило пропускается, в отчёте пометка `rule_failed`.
- Автор комментариев Word — «ГОСТ-сервис», инициалы «ГС».
- Тестовые DOCX генерируются кодом (`tests/builders.py`), бинарные фикстуры в репозиторий не кладём.
- Единицы: поля и отступы в профиле — миллиметры и сантиметры как в ГОСТе (`mm`, `cm`), кегль — `pt`.

## Значения профиля ГОСТ 7.32-2017 (используются в задачах)

| Ключ | value | severity | source |
|---|---|---|---|
| `page.size` | `{"format": "A4", "orientation": "portrait"}` | error | п. 6.1.1 |
| `page.margins` | `{"top_mm": 20, "bottom_mm": 20, "left_mm": 30, "right_mm": 15}` | error | п. 6.1.1 |
| `body.font_name` | `{"name": "Times New Roman"}` | recommendation | п. 6.1.1 |
| `body.font_size` | `{"min_pt": 12, "target_pt": 14}` | error | п. 6.1.1 |
| `body.line_spacing` | `{"multiple": 1.5}` | error | п. 6.1.1 |
| `body.first_line_indent` | `{"cm": 1.25}` | error | п. 6.1.1 |
| `body.alignment` | `{"align": "justify"}` | error | п. 6.1.1 |
| `headings.section` | `{"bold": true, "align": "left", "first_line_indent_cm": 1.25, "trailing_period": false, "page_break_before_level1": true}` | error | п. 6.2.1–6.2.3 |
| `headings.structural` | `{"bold": true, "align": "center", "uppercase": true, "trailing_period": false, "page_break_before": true}` | error | п. 6.2.1 |
| `captions.figure` | `{"pattern": "Рисунок {n} — {title}", "position": "below", "align": "center"}` | error | п. 6.5.5 |
| `captions.table` | `{"pattern": "Таблица {n} — {title}", "position": "above", "align": "left", "first_line_indent_cm": 0}` | error | п. 6.6.3 |
| `page_numbers` | `{"position": "bottom_center", "show_on_first": false}` | error | п. 6.3.1 |

Названия структурных элементов (`headings.structural` применяется к ним): РЕФЕРАТ, СОДЕРЖАНИЕ, ТЕРМИНЫ И ОПРЕДЕЛЕНИЯ, ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ, ВВЕДЕНИЕ, ЗАКЛЮЧЕНИЕ, СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ, ПРИЛОЖЕНИЕ (с буквой).

## Review Focus

1. **Документ без стилей Word** (всё в «Обычном», заголовки — просто жирный текст) — анализатор всё равно должен находить заголовки по эвристикам, иначе «Оформить» испортит их как основной текст. Тест в задаче 3.
2. **Абзацы, где формат задан на уровне run, а не стиля** (каждое слово своим шрифтом) — `check` должен видеть фактический шрифт, `fix` — чистить прямое форматирование run. Тесты в задаче 5.
3. **Таблицы и пустые абзацы** — правила основного текста не должны ставить отступ 1,25 в ячейки таблиц и не должны комментировать пустые абзацы. Тест в задаче 5.
4. **Повторный прогон «Оформить» на уже оформленном документе** — результат идемпотентен, замечаний 0. Тест в задаче 9.
5. **Вставленный текст с Windows-переводами строк, табами и пустыми строками подряд** — импорт не создаёт пустых абзацев-мусора и сохраняет все слова. Тест в задаче 8.

---

### Task 1: Каркас пакета и модель профиля

**Files:**
- Create: `backend/pyproject.toml`, `backend/gostdoc_engine/__init__.py`, `backend/gostdoc_engine/profile.py`, `backend/profiles/gost_7_32_2017.json`, `backend/tests/test_profile.py`, `.gitignore`

**Interfaces:**
- Produces:
  - `class RuleConfig(BaseModel)`: `value: dict`, `severity: Literal["error","recommendation"]`, `enabled: bool = True`, `source: str`
  - `class Profile(BaseModel)`: `id: str`, `name: str`, `base: str | None`, `readonly: bool`, `rules: dict[str, RuleConfig]`
  - `load_profile(path: Path) -> Profile`, `builtin_profile(profile_id: str) -> Profile` (ищет в `backend/profiles/`)
  - `KNOWN_RULE_KEYS: frozenset[str]` — ключи из таблицы выше; `Profile` отклоняет неизвестный ключ (`ValueError`)

- [ ] **Step 1: Тесты**

```python
def test_builtin_gost_732_loads():
    p = builtin_profile("gost-7.32-2017")
    assert p.readonly is True
    assert p.rules["page.margins"].value == {"top_mm": 20, "bottom_mm": 20, "left_mm": 30, "right_mm": 15}
    assert p.rules["body.font_size"].value["min_pt"] == 12

def test_unknown_rule_key_rejected():
    with pytest.raises(ValidationError):
        Profile(id="x", name="x", base=None, readonly=False,
                rules={"nope.rule": {"value": {}, "severity": "error", "source": ""}})

def test_bad_severity_rejected(): ...  # severity="fatal" → ValidationError
```

- [ ] **Step 2:** `cd backend && pip install -e .[dev] && pytest tests/test_profile.py -v` → FAIL (модуль не найден)
- [ ] **Step 3:** `pyproject.toml` (зависимости: python-docx>=1.2, lxml, pydantic>=2; dev: pytest, ruff), `profile.py`, JSON профиля со всеми строками таблицы. `.gitignore`: `__pycache__/`, `.venv/`, `*.egg-info/`, `.pytest_cache/`.
- [ ] **Step 4:** `pytest tests/test_profile.py -v` → PASS; `ruff check .` → чисто
- [ ] **Step 5:** commit «Движок: каркас пакета и модель профиля требований»

### Task 2: Генератор тестовых документов

**Files:**
- Create: `backend/tests/builders.py`, `backend/tests/test_builders.py`

**Interfaces:**
- Produces: `build_docx(blocks: list[Block], *, margins_mm=(20,20,30,15), font="Times New Roman", size_pt=14, line_spacing=1.5, indent_cm=1.25, align="justify", use_heading_styles=True, page_numbers=True) -> docx.Document`
  - `Block` — кортеж `(kind, text)`; kind ∈ `"h1"`, `"h2"`, `"structural"`, `"p"`, `"figure_caption"`, `"table_caption"`, `"table"` (text = «a|b;c|d»), `"empty"`.
  - Параметры по умолчанию дают документ, полностью соответствующий профилю 7.32. Нарушения задаются аргументами.
  - `use_heading_styles=False` — заголовки делаются «Обычным» стилем, жирным run.
  - `save(doc) -> bytes`

- [ ] **Step 1: Тест** — `build_docx([("structural","ВВЕДЕНИЕ"),("p","Текст.")])` сохраняется и открывается; поля секции = 20/20/30/15 мм (±0,1 мм); у абзаца «Текст.» first_line_indent = 1,25 см.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS
- [ ] **Step 5:** commit «Тесты: генератор DOCX-фикстур»

### Task 3: Модель документа и анализ ролей

**Files:**
- Create: `backend/gostdoc_engine/model.py`, `backend/gostdoc_engine/analyze.py`, `backend/tests/test_analyze.py`

**Interfaces:**
- Consumes: `build_docx` (тесты)
- Produces:
  - `class Role(StrEnum)`: `BODY, HEADING_1, HEADING_2, HEADING_3, STRUCTURAL, FIGURE_CAPTION, TABLE_CAPTION, LIST_ITEM, TOC, TITLE_PAGE, EMPTY, IN_TABLE`
  - `@dataclass DocParagraph`: `index: int`, `role: Role`, `text: str`, `para: docx.text.paragraph.Paragraph`
  - `@dataclass DocModel`: `doc: docx.Document`, `paragraphs: list[DocParagraph]`; `by_role(*roles) -> list[DocParagraph]`
  - `analyze(doc: docx.Document) -> DocModel`

Порядок определения роли: абзац внутри таблицы → `IN_TABLE`; пустой → `EMPTY`; стиль `Heading N`/`Заголовок N` → `HEADING_N`; текст (без пробелов по краям, без регистра) совпадает с названием структурного элемента из таблицы выше → `STRUCTURAL`; `^Рисунок\s+\d` / `^Рис\.\s*\d` → `FIGURE_CAPTION`; `^Таблица\s+\d` → `TABLE_CAPTION`; `^\d+(\.\d+){0,2}\.?\s+\S` и длина < 200 и (весь текст жирный или длина < 100 без точки в конце) → `HEADING_{число уровней}`; стиль списка или numPr → `LIST_ITEM`; абзацы до первого `STRUCTURAL`/`HEADING_1`, если в документе есть «СОДЕРЖАНИЕ» или «РЕФЕРАТ» дальше по тексту → `TITLE_PAGE`; строки после «СОДЕРЖАНИЕ» до следующего `STRUCTURAL` → `TOC`; иначе `BODY`.

- [ ] **Step 1: Тесты**
  - `test_roles_with_styles` — документ из всех видов блоков, роли совпадают с ожидаемыми.
  - `test_roles_without_heading_styles` — тот же набор с `use_heading_styles=False`: «1 Обзор» → `HEADING_1`, «1.1 Рынок» → `HEADING_2`, «ВВЕДЕНИЕ» → `STRUCTURAL`.
  - `test_numbered_body_sentence_not_heading` — «1 января компания открыла офис в Москве и наняла сорок сотрудников.» не жирный → `BODY`.
  - `test_table_cells_are_in_table`.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS
- [ ] **Step 5:** commit «Движок: анализ ролей абзацев»

### Task 4: Каркас правил и раннер

**Files:**
- Create: `backend/gostdoc_engine/rules/__init__.py`, `backend/gostdoc_engine/rules/base.py`, `backend/gostdoc_engine/runner.py`, `backend/tests/test_runner.py`

**Interfaces:**
- Consumes: `DocModel`, `Profile`, `RuleConfig`
- Produces:
  - `@dataclass Issue`: `rule: str`, `source: str`, `severity: str`, `message: str` (по-русски, вида «Межстрочный интервал: ожидается 1,5, найдено 1,0»), `expected: str`, `actual: str`, `paragraph_index: int | None`, `fixable: bool`
  - `class Rule(ABC)`: `key: ClassVar[str]`, `fixable: ClassVar[bool]`; `check(self, model: DocModel, cfg: RuleConfig) -> list[Issue]`; `fix(self, model: DocModel, cfg: RuleConfig) -> None` (по умолчанию `NotImplementedError`)
  - `register(rule_cls)` — декоратор, `REGISTRY: dict[str, type[Rule]]`
  - `@dataclass RunResult`: `issues: list[Issue]`, `failed_rules: list[str]`
  - `run_check(model, profile) -> RunResult`, `run_fix(model, profile) -> None` — пропускают `enabled=False` и ключи без зарегистрированного правила; исключение правила → ключ в `failed_rules`, лог через `logging`, продолжение.

- [ ] **Step 1: Тесты** — с тестовыми правилами, зарегистрированными в фикстуре: отключённое правило не вызывается; правило, бросающее исключение, попадает в `failed_rules`, а следующее правило отрабатывает; `run_fix` не вызывает `fix` у `fixable=False`.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS
- [ ] **Step 5:** commit «Движок: каркас правил и раннер»

### Task 5: Правила страницы и основного текста

**Files:**
- Create: `backend/gostdoc_engine/rules/page.py`, `backend/gostdoc_engine/rules/body.py`, `backend/gostdoc_engine/units.py`, `backend/tests/test_rules_page.py`, `backend/tests/test_rules_body.py`

**Interfaces:**
- Consumes: `Rule`, `register`, `Issue`, `DocModel.by_role`
- Produces: правила с ключами `page.size`, `page.margins`, `body.font_name`, `body.font_size`, `body.line_spacing`, `body.first_line_indent`, `body.alignment` (все `fixable=True`); `units.effective_font_name(par) -> str | None`, `units.effective_font_size_pt(par) -> float | None` — учитывают run → стиль абзаца → стили документа по умолчанию; при разных значениях в run возвращают значение, занимающее больше всего символов.

Правила `body.*` применяются к ролям `BODY` и `LIST_ITEM` (у `LIST_ITEM` не проверяется `first_line_indent`). Допуски: поля ±0,5 мм, отступ ±0,05 см, интервал ±0,05. `body.font_size`: ошибка, если меньше `min_pt`; `fix` ставит `target_pt` только тем абзацам, где кегль < `min_pt`. `fix` шрифта и кегля убирает прямое форматирование run (`rFonts`, `sz`, `szCs`) и задаёт значение на уровне абзаца/стиля. Одно замечание на правило на абзац; соседние абзацы с одинаковым нарушением — тоже отдельные замечания (группировка — забота отчёта).

- [ ] **Step 1: Тесты (на каждое правило)** — `check` на корректном документе → `[]`; на документе с нарушением (например `margins_mm=(20,20,20,10)`, `font="Arial"`, `size_pt=11`, `line_spacing=1.0`, `indent_cm=0`, `align="left"`) → замечание с нужными `expected`/`actual`; после `fix` → `check` пуст.
  - `test_run_level_font_detected_and_fixed` — абзац, у которого стиль Times, а каждый run — Arial.
  - `test_table_cells_and_empty_paragraphs_ignored` — нет замечаний `body.first_line_indent` на ячейках и пустых абзацах.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS
- [ ] **Step 5:** commit «Правила: страница и основной текст»

### Task 6: Правила заголовков, подписей и нумерации страниц

**Files:**
- Create: `backend/gostdoc_engine/rules/headings.py`, `backend/gostdoc_engine/rules/captions.py`, `backend/gostdoc_engine/rules/page_numbers.py`, тесты `test_rules_headings.py`, `test_rules_captions.py`, `test_rules_page_numbers.py`

**Interfaces:**
- Produces: правила `headings.section` (роли `HEADING_1..3`), `headings.structural` (`STRUCTURAL`), `captions.figure`, `captions.table`, `page_numbers`.
  - `headings.*`, `page_numbers` — `fixable=True`. `fix` заголовка: жирность, выравнивание, отступ, удаление точки в конце, `uppercase` (только для `STRUCTURAL`), `page_break_before`.
  - `captions.*` — `check` сравнивает текст с `pattern` (разрешённые варианты тире: «—», «–», «-»; ожидается «—»), выравнивание и положение относительно рисунка/таблицы (подпись таблицы — абзац непосредственно перед таблицей; подпись рисунка — абзац сразу после абзаца с рисунком `w:drawing`). `fix`: только тире и выравнивание (типографика разрешена); положение — только замечание.
  - `page_numbers.fix` — поле `PAGE` в нижнем колонтитуле по центру, `titlePg` для скрытия на первой странице.

- [ ] **Step 1: Тесты** — по схеме задачи 5 для каждого правила; плюс `test_caption_wrong_dash_fixed` («Рисунок 1 - Схема» → «Рисунок 1 — Схема»), `test_table_caption_after_table_reported_not_moved`, `test_no_page_numbers_added`.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS
- [ ] **Step 5:** commit «Правила: заголовки, подписи, нумерация страниц»

### Task 7: Комментарии Word

**Files:**
- Create: `backend/gostdoc_engine/comments.py`, `backend/tests/test_comments.py`

**Interfaces:**
- Consumes: `Issue`, `DocModel`
- Produces: `add_comments(model: DocModel, issues: list[Issue]) -> int` — число добавленных комментариев. Использует `docx.Document.add_comment(runs, text, author="ГОСТ-сервис", initials="ГС")`. Текст: `"[{source}] {message}"`. Замечания с одним `paragraph_index` объединяются в один комментарий (строки через перевод строки). Замечания без абзаца (`page.*`) — комментарий к первому непустому абзацу. Абзац без run получает пустой run для привязки.

- [ ] **Step 1: Тест** — после `add_comments` и сохранения/перечитывания в `word/comments.xml` есть нужное число комментариев с автором «ГОСТ-сервис» и текстом, содержащим `source`.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS
- [ ] **Step 5:** commit «Движок: замечания комментариями Word»

### Task 8: Импорт DOCX и обычного текста

**Files:**
- Create: `backend/gostdoc_engine/importer.py`, `backend/tests/test_importer.py`

**Interfaces:**
- Produces:
  - `class InputError(Exception)` — сообщение по-русски для пользователя.
  - `MAX_BYTES = 20 * 1024 * 1024`
  - `load_docx(data: bytes) -> docx.Document` — `InputError("Файл больше 20 МБ")`, `InputError("Файл не похож на документ Word (.docx)")` для не-ZIP/битого, `InputError("Документ защищён паролем — снимите защиту и загрузите снова")` для OLE-контейнера с `EncryptedPackage`.
  - `text_to_docx(text: str) -> docx.Document` — нормализует `\r\n`/`\r` → `\n`, табы → пробел; абзацы разделяются пустыми строками или переводом строки; несколько пустых строк подряд не порождают пустых абзацев; распознанные (по правилам задачи 3) заголовки получают стили `Heading 1/2/3`, структурные элементы — `Heading 1`.

- [ ] **Step 1: Тесты** — превышение размера, мусорные байты, зашифрованный файл (минимальный OLE-заголовок `D0 CF 11 E0`), `text_to_docx("ВВЕДЕНИЕ\r\n\r\n\r\nТекст\tработы.\n1 Обзор\nЕщё текст.")` → 4 абзаца, роли `STRUCTURAL, BODY, HEADING_1, BODY`, все слова на месте.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS
- [ ] **Step 5:** commit «Движок: импорт DOCX и обычного текста»

### Task 9: Конвейер, инвариант текста и CLI

**Files:**
- Create: `backend/gostdoc_engine/pipeline.py`, `backend/gostdoc_engine/textguard.py`, `backend/gostdoc_engine/__main__.py`, `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: всё выше.
- Produces:
  - `textguard.normalized_words(doc) -> list[str]` — текст всех абзацев (включая таблицы), где кавычки «»„“"' → `"`, тире —–‑ → `-`, все пробельные (включая неразрывный) схлопнуты; разбит на слова.
  - `class TextChangedError(Exception)`
  - `@dataclass ProcessResult`: `docx_bytes: bytes`, `report: dict` (`{"profile": id, "mode": ..., "issues": [asdict(Issue)...], "failed_rules": [...], "summary": {"errors": n, "recommendations": n}}`)
  - `process(data: bytes | str, profile: Profile, mode: Literal["check","format"]) -> ProcessResult` — `str` → `text_to_docx`, `bytes` → `load_docx`; `analyze`; для `format`: `run_fix`, повторный `analyze`, сверка `normalized_words` до/после (`TextChangedError` при расхождении); `run_check`; `add_comments`; сохранение.
  - CLI: `python -m gostdoc_engine IN [--text] --profile gost-7.32-2017|path.json --mode check|format -o OUT.docx [--report OUT.json]`; код выхода 2 и сообщение на русском при `InputError`.

- [ ] **Step 1: Тесты**
  - `test_format_fixes_all_fixable` — документ с нарушениями всех автоисправимых правил → в отчёте после `format` нет замечаний с `fixable=True`.
  - `test_format_is_idempotent` — повторный `format` результата → 0 замечаний, `docx` без новых комментариев.
  - `test_check_does_not_modify_formatting` — после `check` поля и шрифты те же, что на входе.
  - `test_text_preserved` — `normalized_words` входа и выхода совпадают на всех фикстурах из задач 3–6.
  - `test_custom_profile` — копия 7.32 с `body.font_size.target_pt=12`, `min_pt=12` и `page.margins.left_mm=25` → документ с полем 25 мм и кеглем 12 проходит без ошибок.
  - `test_cli_smoke` — `subprocess` вызывает CLI на `--text` входе, файл и JSON созданы, код 0.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS
- [ ] **Step 5:** commit «Движок: конвейер, защита текста, CLI»

### Task 10: CI и README

**Files:**
- Create: `.github/workflows/backend-tests.yml`, `README.md`

- [ ] **Step 1:** Workflow: on push/PR, Python 3.12, `pip install -e backend[dev]`, `ruff check backend`, `pytest backend -q`.
- [ ] **Step 2:** README на русском: что за сервис, ссылка на спецификацию, как запустить тесты и CLI с примером.
- [ ] **Step 3:** Локально `ruff check backend && pytest backend -q` → всё зелёное.
- [ ] **Step 4:** commit «CI: тесты движка; README»
