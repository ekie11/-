# Этап 3: фронтенд и гостевой режим — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Веб-интерфейс на Next.js поверх API: пошаговый мастер (документ → требования → результат), вход и регистрация, профили с редактором, история документов; гостевой режим в API для первого документа без регистрации.

**Architecture:** Гостевой режим добавляется в `backend/gostdoc_api` (таблица гостевых сессий, `jobs.guest_id`, лимиты). Фронтенд — отдельное приложение `frontend/` (Next.js App Router, TypeScript, Tailwind), все запросы идут на `/api/*`, которые Next.js проксирует на FastAPI (`API_URL`), поэтому cookie работают на одном домене. Состояние сервера читается в клиентских компонентах через тонкий клиент `lib/api.ts`.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (бэкенд), Node 22, Next.js 16, React 19, TypeScript, Tailwind CSS 4, Vitest + Testing Library + jsdom, Playwright (браузер из `/opt/pw-browsers`).

**Spec:** `docs/specs/2026-10-18-frontend-design.md` (основная — `docs/specs/2026-10-15-gost-formatter-design.md`).

## Global Constraints

- Все тексты интерфейса и сообщения об ошибках — по-русски; ошибки API (`{"detail": "..."}`) показываются как есть.
- Гость: cookie `guest` (httpOnly, SameSite=Lax, Secure по `COOKIE_SECURE`, 24 ч), в БД — только SHA-256 токена; лимит 3 задачи за скользящие 24 ч на гостевую сессию и 10 на IP; превышение → 429 «Зарегистрируйтесь, чтобы продолжить»; только ГОСТ-профили; `expires_at` = +24 ч.
- `TRUSTED_PROXIES` — список CIDR через запятую (по умолчанию пусто); `X-Forwarded-For` учитывается только от доверенного адреса подключения (берётся последний недоверенный адрес справа).
- При регистрации/входе с cookie `guest` задачи гостя переносятся в аккаунт, срок хранения — `FILE_TTL_DAYS`, гостевая сессия удаляется, cookie стирается.
- Чужие задачи (гость↔гость, гость↔пользователь) → 404.
- Фронтенд: папка `frontend/`; без UI-библиотек компонентов; шрифт Inter (`next/font/google`), один акцентный цвет `#1d4ed8`, фон `#ffffff`, текст `#111827`, вторичный текст `#6b7280`, линии `#e5e7eb`; без градиентов и теней.
- Все HTTP-запросы фронтенда идут на относительные пути `/api/...`; `next.config` проксирует `/api/:path*` → `${API_URL}/:path*` (по умолчанию `http://127.0.0.1:8000`).
- Файл в мастере: только `.docx`, ≤ 20 МБ — проверяется на клиенте до отправки (сообщения: «Нужен файл .docx», «Файл больше 20 МБ»).
- Опрос статуса задачи — каждые 2 с, пока статус `queued`/`running`.
- Пакетный менеджер — npm; версии зависимостей фиксируются в `package-lock.json`.

## Review Focus

1. **Гость удалил cookie и пришёл снова** — лимит на IP всё равно действует; новый гость не видит старых задач. Тест в задаче 1.
2. **Вход с гостевым cookie, когда у пользователя уже есть задачи** — переносятся только задачи этой гостевой сессии, чужие гостевые задачи не трогаются. Тест в задаче 1.
3. **Ответ API 401 посреди работы (сессия истекла)** — фронтенд не падает: на защищённых страницах уводит на `/login?next=…`, в мастере продолжает как гость. Тест в задаче 3.
4. **Двойной клик «Запустить»** — создаётся одна задача (кнопка блокируется до ответа). Тест в задаче 4.
5. **Правило профиля без описания в словаре** — форма показывает его в «Другом» и сохраняет без изменений. Тест в задаче 5.

---

### Task 1: Гостевой режим в API

**Files:**
- Create: `backend/gostdoc_api/guest.py`, `backend/gostdoc_api/client_ip.py`, `backend/gostdoc_api/migrations/versions/0002_guest_mode.py`, `backend/tests/api/test_guest.py`
- Modify: `backend/gostdoc_api/models.py` (`GuestSession`; `Job.user_id` nullable, `Job.guest_id`, `Job.client_ip`), `config.py` (`trusted_proxies: tuple[str, ...]`), `routes/jobs.py`, `routes/auth.py`, `cleanup.py`, `docs/API.md`

**Interfaces:**
- Produces:
  - `models.GuestSession(id: int, token_hash: str unique, created_at, expires_at)`.
  - `client_ip.client_ip(request, trusted: tuple[str, ...]) -> str`.
  - `guest.Owner` — dataclass `(user: User | None, guest: GuestSession | None)`; зависимость `owner_or_guest(request, response, db) -> Owner`: пользователь по cookie `session`, иначе существующий гость по cookie `guest`, иначе создаёт гостя и ставит cookie.
  - `guest.check_guest_limits(db, guest, ip, now) -> None` — `HTTPException(429, ...)`.
  - `guest.claim_guest_jobs(db, request, response, user, settings) -> int` — вызывается из `register` и `login`.
  - `routes/jobs.py`: все эндпоинты используют `owner_or_guest`; гость с `profile_id` своего профиля → 404; `GET /jobs` для гостя — только его задачи.

- [ ] **Step 1: Тесты** — гость создаёт задачу без входа (202, cookie `guest` выставлен, в БД только хэш); 4-я задача той же сессии → 429; 11-я с одного IP при разных гостевых cookie → 429; X-Forwarded-For от недоверенного адреса игнорируется, от доверенного — учитывается; гость A не видит задачу гостя B и пользователя (404 на GET/docx/pdf); гость со своим профилем → 404; `expires_at` гостя ≈ +24 ч; регистрация с cookie `guest` переносит его задачи (статус и файлы доступны пользователю, срок ≈ +30 дней, cookie стёрт), а задачи другого гостя не трогает; вход — то же самое; cleanup удаляет просроченные гостевые сессии; миграция `0002` применяется поверх `0001`.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** PASS; весь набор тестов бэкенда зелёный; `ruff check backend`.
- [ ] **Step 5:** commit «API: гостевой режим»

### Task 2: Каркас фронтенда, дизайн-токены, компоненты, прокси

**Files:**
- Create: `frontend/package.json`, `package-lock.json`, `next.config.ts`, `tsconfig.json`, `postcss.config.mjs`, `eslint.config.mjs`, `vitest.config.ts`, `vitest.setup.ts`, `src/app/layout.tsx`, `src/app/globals.css`, `src/app/page.tsx` (временная заглушка мастера), `src/components/ui/{Button,TextField,Switch,Tabs,Steps,ErrorBanner,Select}.tsx`, `src/components/Header.tsx`, `src/lib/api.ts`, `src/lib/api.test.ts`, `src/components/ui/ui.test.tsx`, `frontend/README.md`
- Modify: `.gitignore` (`frontend/node_modules`, `frontend/.next`, `frontend/test-results`, `frontend/playwright-report`)

**Interfaces:**
- Produces:
  - `lib/api.ts`: `class ApiError extends Error { status: number; detail: string }`; `apiFetch<T>(path: string, init?: RequestInit): Promise<T>` — префикс `/api`, `credentials: "include"`, JSON по умолчанию, при `!ok` бросает `ApiError` с `detail` из тела (или «Сервер недоступен, попробуйте позже» при сетевой ошибке / не-JSON); `apiUpload<T>(path, form: FormData)`; типы `Me`, `ProfileSummary`, `Profile`, `RuleConfig`, `JobSummary`, `Job`, `Issue` по ответам API этапа 2.
  - `useMe()` — хук: `{ me: Me | null, loading: boolean, refresh(): Promise<void> }` (401 → `me = null`).
  - UI-компоненты с пропсами: `Button({variant: "primary"|"secondary"|"link", loading?, disabled?, ...})`, `TextField({label, error?, ...input})`, `Switch({checked, onChange, label})`, `Tabs({items: {id,label}[], value, onChange})`, `Steps({steps: string[], current: number})`, `ErrorBanner({message})`, `Select({label, options: {value,label}[], value, onChange})`.
  - `Header` — логотип «ГОСТ-сервис», ссылки «Мои документы», «Мои профили» (если `me`), «Войти» / email + «Выйти».
  - npm-скрипты: `dev`, `build`, `start`, `lint`, `typecheck` (`tsc --noEmit`), `test` (`vitest run`), `e2e` (`playwright test`).

- [ ] **Step 1: Тесты** — `apiFetch`: 200 → JSON; 400 с `detail` → `ApiError(400, detail)`; сетевая ошибка → русское сообщение; `Button` с `loading` заблокирована; `Tabs` вызывает `onChange`; `Steps` помечает текущий шаг `aria-current="step"`.
- [ ] **Step 2:** FAIL → **Step 3:** реализация (`create-next-app` не использовать — файлы вручную, чтобы не тянуть лишнее).
- [ ] **Step 4:** `npm run lint && npm run typecheck && npm test && npm run build` — всё зелёное.
- [ ] **Step 5:** commit «Фронтенд: каркас, токены, базовые компоненты, прокси к API»

### Task 3: Вход, регистрация, выход

**Files:**
- Create: `frontend/src/app/login/page.tsx`, `src/app/register/page.tsx`, `src/components/AuthForm.tsx`, `src/lib/nav.ts`, `src/components/AuthForm.test.tsx`, `src/lib/nav.test.ts`, `src/components/RequireAuth.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError`, `useMe`, UI-компоненты.
- Produces:
  - `nav.safeNext(next: string | null) -> string` — только относительные пути, начинающиеся с одного `/` (не `//`, не схема) → иначе `"/"`.
  - `AuthForm({mode: "login"|"register"})` — email + пароль, ошибка API в `ErrorBanner`, после успеха `refresh()` и переход на `safeNext(?next)`; кнопка блокируется на время запроса.
  - `RequireAuth({children})` — пока `loading` — пусто; `me === null` → `router.replace("/login?next=<текущий путь>")`.
  - «Выйти» в `Header` → `POST /api/auth/logout`, `refresh()`, переход на `/`.

- [ ] **Step 1: Тесты** — `safeNext`: `"/documents"` → он же, `"//evil.com"`, `"https://x"`, `null` → `"/"`; `AuthForm` показывает `detail` из 401; успешный вход вызывает переход на `next`; `RequireAuth` при 401 уводит на `/login?next=/profiles`.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** lint, typecheck, test зелёные
- [ ] **Step 5:** commit «Фронтенд: вход, регистрация, выход»

### Task 4: Мастер и экран результата

**Files:**
- Create: `frontend/src/app/page.tsx` (заменяет заглушку), `src/components/wizard/{Wizard,StepDocument,StepRequirements,FileDrop}.tsx`, `src/app/jobs/[id]/page.tsx`, `src/components/result/{JobResult,IssueList}.tsx`, `src/lib/wizard.ts`, `src/lib/issues.ts`, тесты `src/lib/wizard.test.ts`, `src/lib/issues.test.ts`, `src/components/wizard/Wizard.test.tsx`, `src/components/result/JobResult.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `apiUpload`, `useMe`, UI-компоненты.
- Produces:
  - `wizard.validateFile(file: File) -> string | null` — «Нужен файл .docx» / «Файл больше 20 МБ» / `null`.
  - `wizard.stepFromQuery(step: string | null, hasInput: boolean) -> 1 | 2` — шаг 2 только при наличии введённого документа, иначе 1.
  - `issues.groupIssues(issues: Issue[]) -> {rule: string, source: string, items: Issue[]}[]` (порядок первого появления) и `issues.summary(report) -> string` — «N замечаний: X исправлено, Y требуют вашего решения» (для режима check — «N замечаний»; склонение «замечание/замечания/замечаний»).
  - Шаг 1: вкладки «Загрузить DOCX» / «Вставить текст»; «Далее» активна при валидном файле или непустом тексте.
  - Шаг 2: профили из `GET /api/profiles` (гостю API отдаёт только ГОСТ-профили, см. Decision ниже); режим «Проверить» / «Оформить»; «Запустить» → `POST /api/jobs`, кнопка заблокирована до ответа, переход на `/jobs/{id}`; 429 → `ErrorBanner` с текстом и ссылкой «Зарегистрироваться».
  - **Decision:** `GET /profiles` в API становится доступен гостю и возвращает только ГОСТ-профили (правка `routes/profiles.py` входит в эту задачу, с тестом в `backend/tests/api/test_profiles.py`).
  - Результат: опрос `GET /api/jobs/{id}` каждые 2 с при `queued`/`running`; `done` — сводка, `IssueList`, `<iframe src="/api/jobs/{id}/pdf">` если `has_pdf`, ссылки на `/api/jobs/{id}/docx` и `/pdf`; `error` — текст и «Попробовать снова» (на `/`); гостю — плашка «Результат хранится 24 часа — зарегистрируйтесь, чтобы сохранить» со ссылкой `/register?next=/jobs/{id}`.

- [ ] **Step 1: Тесты** — `validateFile` (pdf, 21 МБ, ok); `stepFromQuery`; `groupIssues` и `summary` (1/2/5/21 замечание); `Wizard`: «Далее» неактивна без ввода, текст → шаг 2, двойной клик «Запустить» шлёт один запрос, 429 показывает текст; `JobResult`: `running` → опрашивает (fake timers), `done` → сводка и ссылки, `error` → текст; бэкенд-тест: гость получает только ГОСТ-профили.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** lint, typecheck, test, build; pytest бэкенда
- [ ] **Step 5:** commit «Фронтенд: мастер и экран результата»

### Task 5: Профили и редактор

**Files:**
- Create: `frontend/src/app/profiles/page.tsx`, `src/app/profiles/[id]/page.tsx`, `src/lib/ruleSchema.ts`, `src/lib/profileForm.ts`, `src/components/profile/{ProfileEditor,RuleRow,GroupNav}.tsx`, тесты `src/lib/ruleSchema.test.ts`, `src/lib/profileForm.test.ts`, `src/components/profile/ProfileEditor.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `apiUpload`, `RequireAuth`, типы `Profile`, `RuleConfig`.
- Produces:
  - `ruleSchema.GROUPS` — 10 групп из спецификации в порядке; `ruleSchema.FIELDS: FieldDef[]`, `FieldDef = {rule: string, path: string, group: GroupId, label: string, kind: "number"|"select"|"bool"|"text", unit?: string, min?: number, max?: number, step?: number, options?: {value: string, label: string}[]}` — описывает каждое поле `value` всех 12 правил профиля `backend/profiles/gost_7_32_2017.json` (поля в мм 0–50, кегль 8–20, интервал 1–3 шаг 0,05, отступ 0–3 см шаг 0,05; выравнивание: justify/left/center/right — «по ширине/по левому краю/по центру/по правому краю»).
  - `profileForm.getAt(value, path)`, `setAt(value, path, v)` (иммутабельно), `differs(rule, baseRule) -> boolean`, `groupHasDiff(profile, base, group) -> boolean`, `unknownRules(profile) -> string[]` (правила без описаний).
  - `/profiles`: список своих профилей (`RequireAuth`), «Создать на основе ГОСТа» (выбор ГОСТа → `POST /api/profiles {base_id, name}` → переход в редактор), «Импорт» (`POST /api/profiles/import`).
  - `/profiles/{id}`: `ProfileEditor` по спецификации, раздел 4; базовый профиль для сравнения — `GET /api/profiles/{base}`; «Сохранить» → `PUT` всего профиля; `beforeunload` при несохранённых изменениях; ГОСТ — только чтение и «Создать свой на основе»; «Экспорт JSON» — ссылка на `/api/profiles/{id}/export`; «Удалить» с `confirm`. Параметр `?return=wizard` после сохранения возвращает на `/?step=2&profile={id}`.
  - Мастер (шаг 2) принимает `?profile=` для предвыбора и показывает ссылку «Настроить свои требования» → `/profiles?return=wizard`.

- [ ] **Step 1: Тесты** — каждое поле `FIELDS` указывает на существующий путь в JSON ГОСТ-профиля (тест читает `../backend/profiles/gost_7_32_2017.json`); `setAt` не мутирует; `differs`/`groupHasDiff`; `ProfileEditor`: изменение «Левое поле» подсвечивает строку и точку группы, «вернуть как в ГОСТе» снимает подсветку, «Сохранить» шлёт `PUT` с изменённым значением, правило без описания показывается в «Другом» и сохраняется без изменений, ГОСТ-профиль — поля отключены.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** lint, typecheck, test, build
- [ ] **Step 5:** commit «Фронтенд: профили и редактор требований»

### Task 6: История документов

**Files:**
- Create: `frontend/src/app/documents/page.tsx`, `src/components/DocumentsTable.tsx`, `src/lib/format.ts`, тесты `src/lib/format.test.ts`, `src/components/DocumentsTable.test.tsx`

**Interfaces:**
- Produces:
  - `format.dateTime(iso) -> string` (`ru-RU`, «18 окт. 2026, 14:05»), `format.statusLabel(status)` — queued «В очереди», running «Обрабатывается», done «Готово», error «Ошибка», expired «Срок хранения истёк»; `format.modeLabel` — «Проверка»/«Оформление».
  - `/documents` (`RequireAuth`): таблица из `GET /api/jobs` — дата, профиль, режим, статус, «хранится до»; строка ведёт на `/jobs/{id}`; пустое состояние «Пока нет документов» со ссылкой на мастер.

- [ ] **Step 1: Тесты** — `statusLabel` для всех статусов; таблица рендерит строки и пустое состояние.
- [ ] **Step 2:** FAIL → **Step 3:** реализация → **Step 4:** lint, typecheck, test, build
- [ ] **Step 5:** commit «Фронтенд: история документов»

### Task 7: Сквозные тесты и CI

**Files:**
- Create: `frontend/playwright.config.ts`, `frontend/e2e/guest.spec.ts`, `frontend/e2e/user.spec.ts`, `frontend/e2e/start-stack.sh`, `.github/workflows/frontend.yml`
- Modify: `README.md`, `frontend/README.md`

**Interfaces:**
- Produces:
  - `start-stack.sh` — поднимает для тестов: `redis-server` на свободном порту, SQLite во временном каталоге, `python -m gostdoc_api migrate`, `serve` на `:8000`, `worker`, `SOFFICE_PATH` = фиктивный скрипт, пишущий минимальный PDF; `COOKIE_SECURE=false`; при выходе убивает всё.
  - `playwright.config.ts` — `webServer`: `start-stack.sh` и `npm run build && npm run start` на `:3000`; Chromium из `PLAYWRIGHT_BROWSERS_PATH` (локально `executablePath: '/opt/pw-browsers/chromium'`, если задан `PW_CHROMIUM`).
  - `guest.spec.ts`: открыть `/` → «Вставить текст» → текст «ВВЕДЕНИЕ\n\nТекст работы.» → «Далее» → ГОСТ 7.32 → «Проверить» → «Запустить» → дождаться сводки → ссылка «Скачать DOCX» отдаёт файл.
  - `user.spec.ts`: регистрация → «Мои профили» → «Создать на основе ГОСТа» → поменять «Левое поле» на 25 → «Сохранить» → мастер с этим профилем → «Оформить» → результат готов → в «Мои документы» есть задача.
  - `frontend.yml`: Node 22, `npm ci`, lint, typecheck, test, build; затем Python 3.12, `pip install -e backend[dev]`, `redis-server` (service container), `npx playwright install --with-deps chromium`, `npm run e2e`.

- [ ] **Step 1:** Написать сценарии и конфигурацию.
- [ ] **Step 2:** Прогнать локально `npm run e2e` — оба сценария зелёные (приложить вывод в отчёт).
- [ ] **Step 3:** Обновить README (как запустить фронтенд локально вместе с API).
- [ ] **Step 4:** commit «Фронтенд: сквозные тесты и CI»
