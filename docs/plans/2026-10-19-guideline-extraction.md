# Профиль из методички (ИИ) — план

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Пользователь загружает методичку (DOCX/PDF/текст) → модель GLM извлекает требования с цитатами → сервер проверяет их → пользователь отмечает строки в таблице → создаётся профиль и открывается редактор.

**Architecture:** Один запрос к OpenAI-совместимому API на методичку в задаче RQ; ответ проверяется по единому описанию полей `backend/profiles/fields.json` (пределы + дословная цитата в тексте). Описание полей отдаётся фронтенду через `GET /profile-fields` и заменяет `ruleSchema.ts`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/Alembic, RQ, httpx, pypdf, python-docx; Next.js 16, Vitest, Playwright.

**Spec:** `docs/specs/2026-10-19-guideline-extraction-design.md`

## Global Constraints

- Переменные окружения (в `Settings` и `.env.example`): `LLM_BASE_URL` (по умолчанию `https://open.bigmodel.cn/api/paas/v4`), `LLM_API_KEY` (пусто = функция выключена), `LLM_MODEL=glm-4.6`, `LLM_TIMEOUT_S=120`, `EXTRACT_USER_DAILY=5`, `EXTRACT_GLOBAL_DAILY=500`.
- Лимит текста методички 150 000 символов; файл до 20 МБ; PDF с < 200 символов текста — «В PDF нет текста — похоже на скан».
- Все сообщения пользователю — по-русски, тексты ошибок из спецификации дословно.
- Ни ключ, ни текст методички не пишутся в логи, БД и на диск; хранится только результат с цитатами.
- Настоящая модель в тестах не вызывается (подмена транспорта httpx / функции `chat_json`).
- `pypdf` и `httpx` — в основные зависимости `backend/pyproject.toml`.
- Поля `kind: "fixed"` модели не предлагаются и из ответа отбрасываются.

## Review Focus

1. Цитата с другими кавычками/тире/переносами строк, чем в тексте («“30 мм”» vs ««30 мм»», перенос посреди фразы) — должна находиться. Тест в задаче 3.
2. Модель вернула значение строкой («30», «1,5») или с единицами («14 пт») — приводится к числу; «полуторный» интервал → 1.5 не угадываем: невалидно → отброшено. Тест в задаче 3.
3. Пользователь снял все галочки и нажал «Создать профиль» — создаётся копия базового профиля без ошибок. Тест в задаче 4.
4. Повторный `POST /extractions/{id}/profile` — второй профиль создаётся (не 500), имя дублируется допустимо. Тест в задаче 4.
5. Воркер упал не из-за `LlmError` (исключение в коде) — задача `failed` с общим текстом, лимит засчитан, ошибка не теряется в статусе `running`. Тест в задаче 4.

---

### Task 1: Единое описание полей — `fields.json` и `GET /profile-fields`

**Files:** Create `backend/profiles/fields.json`, `backend/gostdoc_api/fields.py`, `backend/tests/api/test_profile_fields.py`, `frontend/src/lib/fields.ts` (+ тест); Modify `routes/profiles.py` (новый эндпоинт), `frontend/src/lib/ruleSchema.ts` (удалить данные, оставить типы или удалить файл), `RuleRow.tsx`, `ProfileEditor.tsx`, `profileForm.ts`, `ruleSchema.test.ts` → перенос проверок в бэкенд.

**Interfaces:**
- `fields.json`: `{"groups": [{id, label}], "rule_labels": {rule: label}, "fields": [FieldDef]}` — те же данные, что сейчас в `ruleSchema.ts` (GROUPS, RULE_LABELS, FIELDS), в JSON один к одному.
- `fields.load_fields() -> dict` (кэш); `fields.field_index() -> dict[tuple[str,str], dict]`.
- `GET /profile-fields` (без авторизации) → `{...fields.json, "extraction_enabled": bool(settings.llm_api_key)}`.
- Фронтенд: `useProfileFields()` → `{groups, ruleLabels, fields, extractionEnabled}` | загрузка/ошибка; редактор показывает «Загрузка…» до ответа.

- [ ] Тесты бэкенда: эндпоинт отдаёт группы и поля; `extraction_enabled` false без ключа и true с ключом; **каждый лист `value` каждого встроенного профиля описан в `fields`, каждый путь существует** (перенос из `ruleSchema.test.ts`). Тест фронтенда: редактор рендерит поля из подменённого ответа API.
- [ ] FAIL → реализация → `pytest` весь зелёный; `npm run lint && npm run typecheck && npm test && npm run build`; `PYTHON=/usr/bin/python3 npm run e2e`.
- [ ] commit «Описание полей профиля — в бэкенде, GET /profile-fields»

### Task 2: Клиент модели и извлечение текста

**Files:** Create `backend/gostdoc_api/llm.py`, `backend/gostdoc_api/guideline_text.py`, `backend/tests/api/test_llm.py`, `backend/tests/api/test_guideline_text.py`; Modify `config.py`, `pyproject.toml`, `.env.example`.

**Interfaces:**
- `class LlmError(Exception)`; `chat_json(system: str, user: str, *, settings: Settings, transport: httpx.BaseTransport | None = None) -> dict`. POST `{LLM_BASE_URL}/chat/completions`, тело: `model`, `messages`, `temperature: 0`, `response_format: {"type": "json_object"}`, `thinking: {"type": "disabled"}`; заголовок `Authorization: Bearer`. Разбор `choices[0].message.content` как JSON (допускается обёртка в ```json …```). Одна повторная попытка при `httpx.HTTPError`, статусе ≥ 500 или 429, невалидном JSON; 4xx кроме 429 — сразу `LlmError`.
- `class GuidelineError(Exception)` (сообщение — русский текст для пользователя, атрибут `status` 400 или 413); `extract_text(data: bytes, filename: str) -> str` (`.docx`, `.pdf`, иначе «Поддерживаются DOCX и PDF»); `check_text(text: str) -> str` (пустой → «Текст методички пуст», > 150 000 → 413 «Методичка слишком большая — до 150 000 символов (~60 страниц)»). PDF: перед текстом каждой страницы строка `[стр. N]`.

- [ ] Тесты: тело запроса содержит модель, `temperature`, `thinking` disabled и ключ в заголовке; 500 → повтор → успех; два невалидных JSON → `LlmError`; 401 → `LlmError` без повтора; ответ в ```json``` разбирается. DOCX с абзацем и таблицей → оба текста по порядку; PDF из 2 страниц (генерировать в тесте через LibreOffice не нужно — минимальный PDF через `pypdf`/фикстуру-байты) → метки `[стр. 1]`, `[стр. 2]`; PDF без текста → «похоже на скан»; 150 001 символ → 413.
- [ ] FAIL → реализация → весь `pytest` зелёный, `ruff check` чистый.
- [ ] commit «Клиент модели (OpenAI-совместимый) и извлечение текста методички»

### Task 3: Промпт и проверка ответа

**Files:** Create `backend/gostdoc_api/extraction.py`, `backend/tests/api/test_extraction.py`, `backend/scripts/try_extraction.py`.

**Interfaces:**
- Consumes: `fields.load_fields()`, `llm.chat_json`, `guideline_text.extract_text/check_text`.
- `build_messages(text: str) -> tuple[str, str]` — системный промпт по спецификации §3.3 со списком полей без `fixed` (ключ, путь, подпись, тип, единицы, пределы, варианты) и JSON-схемой ответа `{"found": [{"rule","path","value","quote"}], "unsupported": [{"text","quote"}]}`; user = `<<<МЕТОДИЧКА\n{text}\nМЕТОДИЧКА>>>`.
- `validate(raw: dict, text: str) -> dict` → `{"found": [{"rule","path","value","quote","page"}], "unsupported": [...], "rejected_count": int}`. Нормализация для поиска цитаты: нижний регистр; `«»“”„"` → `"`; `—–‑-` → `-`; ё→е; любые пробельные последовательности → один пробел; цитата ≥ 8 символов после нормализации. Приведение: number — `float` из строки с запятой и без единиц (`re` первое число), в `[min, max]`; select — значение из `options`; bool — `true/false` или строки «да/нет»; text — непустая строка ≤ 200. `page` — номер последней метки `[стр. N]` перед позицией цитаты в нормализованном тексте, иначе `None`.
- `run_extraction(text: str, settings: Settings) -> dict` = `validate(chat_json(*build_messages(text)), text)`.
- `scripts/try_extraction.py <файл>` — читает ключ из окружения, печатает таблицу найденного и `rejected_count`.

- [ ] Тесты `validate`: верная строка проходит с `page`; выдуманная цитата, неизвестное поле, поле `fixed`, число вне пределов, select не из вариантов — отброшены и посчитаны; дубликат поля — остаётся первое; **Review Focus 1** (другие кавычки/тире/перенос строки) — находится; **Review Focus 2** («1,5» → 1.5, «14 пт» → 14, «полуторный» → отброшено); `unsupported` без найденной цитаты — отброшено. `build_messages`: в system нет полей `fixed`, текст в разделителях.
- [ ] FAIL → реализация → весь `pytest` зелёный.
- [ ] commit «Извлечение требований: промпт и проверка ответа модели»

### Task 4: API извлечений, лимиты, воркер

**Files:** Create `backend/gostdoc_api/routes/extractions.py`, `backend/gostdoc_api/migrations/versions/0003_extractions.py`, `backend/tests/api/test_extractions.py`; Modify `models.py` (`Extraction`), `worker.py` (`run_extraction_job`), `app.py`, `cleanup.py`, `docs/API.md`.

**Interfaces:**
- `Extraction`: `id: str` (uuid hex), `user_id` FK users CASCADE, `status` queued|running|done|failed, `base_profile_id: str`, `source_name: str | None`, `result: JSONType | None`, `error: Text | None`, `counts_toward_limit: bool = True`, `created_at`.
- `POST /extractions` (multipart `file` | `text`, `base_profile_id`, по умолчанию `gost-7.32-2017`): порядок проверок и тексты — спецификация §3.4; лимиты: user → 429 «Лимит извлечений на сегодня исчерпан», global → 429 «Сервис перегружен, попробуйте завтра»; `queue.enqueue(run_extraction_job, id, text)` → `202 {"id"}`.
- `GET /extractions/quota` → `{"used": int, "limit": int}`; `GET /extractions/{id}` → `{id, status, base_profile_id, source_name, result, error}`; `POST /extractions/{id}/profile` `{accepted: list[int], name: str}` → 409, если не `done`; профиль = `deepcopy` базового, `id` новый, `base_id` = база, для каждого принятого `found[i]` — `rules[rule].value[path] = value` (и `enabled = true`), затем существующая валидация `Profile` и `profiles_service.save_new` → `201 {"profile_id"}`; индекс вне диапазона → 400.
- `worker.run_extraction_job(extraction_id: str, text: str) -> None`: running → `run_extraction` → done; `LlmError` → failed, «Сервис распознавания временно недоступен, попробуйте позже», `counts_toward_limit=False`; другое исключение → failed, «Не удалось обработать методичку», лимит засчитан.
- `cleanup`: удалять извлечения старше `FILE_TTL_DAYS`.

- [ ] Тесты (`chat_json` подменён monkeypatch): гость → 401; без ключа → 503; 6-е за сутки → 429 user; global при `EXTRACT_GLOBAL_DAILY=2` → 429; `LlmError` → failed и лимит не тратится; чужое извлечение → 404; сборка профиля из 2 принятых строк — значения в профиле, остальное как в базе; **Review Focus 3** (пустой `accepted`); **Review Focus 4** (дважды); **Review Focus 5** (исключение в `validate`); скан-PDF → 400 и в БД ничего; quota считает только `counts_toward_limit`; миграция применяется (`alembic upgrade head` в существующем тесте миграций).
- [ ] FAIL → реализация → весь `pytest` зелёный; `docs/API.md` дополнен.
- [ ] commit «API извлечения требований из методички: лимиты, воркер»

### Task 5: Фронтенд — страница «Создать из методички»

**Files:** Create `frontend/src/app/profiles/from-guideline/page.tsx`, `frontend/src/components/extraction/{UploadStep,ResultTable}.tsx` (+ тесты), e2e-сценарий в `frontend/e2e/`, заглушка модели для e2e `frontend/e2e/fake_llm.py` (HTTP-сервер, отдаёт фиксированный JSON); Modify `frontend/src/app/profiles/page.tsx`, `frontend/src/lib/api.ts`, конфиг e2e (запуск заглушки, `LLM_BASE_URL`/`LLM_API_KEY` для API).

**Interfaces:** `api.createExtraction(form: FormData) -> {id}`, `api.getExtraction(id)`, `api.getQuota()`, `api.createProfileFromExtraction(id, {accepted, name}) -> {profile_id}`; поведение и тексты экрана — спецификация §4.

- [ ] Vitest: таблица — галочки включены по умолчанию, строка со значением как в базе приглушена, «Снять все» → `accepted = []`, блок «не поддерживается» без галочек, пустой `found` → «Не нашли требований…»; кнопка на `/profiles` скрыта при `extractionEnabled=false`. e2e: вход → «Создать из методички» → вставить текст → таблица → «Создать профиль» → редактор показывает извлечённое значение поля.
- [ ] `npm run lint && npm run typecheck && npm test && npm run build`; `PYTHON=/usr/bin/python3 npm run e2e`.
- [ ] commit «Фронтенд: создание профиля из методички»
