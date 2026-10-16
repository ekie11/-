# GOSTDoc: проверка и оформление документов по ГОСТ

Сервис для студентов и авторов учебных и технических работ. Загружаете DOCX
или вставляете обычный текст, выбираете требования — готовый ГОСТ (по умолчанию
ГОСТ 7.32-2017) или свой профиль — и получаете либо отчёт с замечаниями, либо
оформленный DOCX.

## Текущее состояние

Сейчас готов **этап 1: движок и CLI** (пакет `gostdoc_engine`). Веб-API и
фронтенд будут добавлены на следующих этапах.

- Режим **«Проверить»** (`--mode check`): замечания добавляются в DOCX как
  комментарии Word, отчёт можно сохранить в JSON.
- Режим **«Оформить»** (`--mode format`): документ приводится к требованиям
  профиля. Текст документа не меняется.

## Документы проекта

- Спецификация: [docs/specs/2026-10-15-gost-formatter-design.md](docs/specs/2026-10-15-gost-formatter-design.md)
- План этапа 1: [docs/plans/2026-10-15-stage1-engine.md](docs/plans/2026-10-15-stage1-engine.md)

## Установка

Требуется Python 3.12 или новее.

```bash
pip install -e "backend[dev]"
```

## Тесты и линтер

Из корня репозитория:

```bash
ruff check backend
cd backend && pytest -q
```

В GitHub Actions эти же проверки запускаются на каждый push и pull request
(файл `.github/workflows/backend-tests.yml`).

## Использование CLI

Общий вид команды:

```bash
python -m gostdoc_engine IN [--text] --profile ID|путь.json --mode check|format -o OUT [--report REPORT]
```

- `IN` — входной файл (DOCX, либо текст при `--text`);
- `--profile` — ID встроенного профиля (по умолчанию `gost-7.32-2017`) или путь к JSON-профилю;
- `--mode` — `check` или `format` (обязательный);
- `-o` — выходной DOCX;
- `--report` — необязательный путь для JSON-отчёта.

Проверка DOCX:

```bash
python -m gostdoc_engine thesis.docx --mode check -o thesis_checked.docx --report report.json
```

Оформление текста из обычного файла:

```bash
python -m gostdoc_engine essay.txt --text --mode format -o essay.docx
```
