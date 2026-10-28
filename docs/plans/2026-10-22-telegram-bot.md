# Telegram-бот и вход через Telegram — план

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Бот в Telegram (оформление, профили, история, методичка) и вход через Telegram на сайте; аккаунт = Telegram ID.

**Architecture:** API принимает запросы бота по внутреннему секрету + Telegram ID (пользователь создаётся автоматически) и вход через виджет Telegram. Бот — отдельный контейнер на aiogram 3 (long polling), всё делает через существующий API по `http://api:8000`; состояние диалога — в Redis.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/Alembic, aiogram 3, httpx, Redis; Next.js 16; docker-compose, Caddy.

**Spec:** `docs/specs/2026-10-22-telegram-bot-design.md`

## Global Constraints

- Переменные: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `BOT_API_SECRET`, `SITE_URL` — в `Settings`, `.env.example` (без значений), `docker-compose.yml`.
- Заголовки бота: `X-Bot-Secret`, `X-Telegram-User`, `X-Telegram-Name`; сравнение секрета `hmac.compare_digest`; пустой `BOT_API_SECRET` = вход бота выключен.
- Caddy удаляет эти три заголовка у всех внешних запросов.
- Подпись виджета: `secret = SHA256(TELEGRAM_BOT_TOKEN)`, HMAC-SHA256 от `data_check_string` (поля кроме `hash`, сортировка, `key=value` через `\n`); `auth_date` не старше 86400 с.
- Тексты ошибок (дословно): «Не удалось подтвердить вход через Telegram» (401), «Этот Telegram уже привязан к другому аккаунту» (409), «Файл больше 20 МБ», «Сервис временно недоступен, попробуйте позже».
- Без `TELEGRAM_BOT_TOKEN`: `/auth/telegram*` → 503, `GET /config` → `{"telegram_bot_username": null}`, бот завершается с сообщением в лог.
- Токен, секрет, документы пользователей не пишутся в логи; бот не сохраняет файлы на диск.
- Настоящий Telegram в тестах не вызывается.

## Review Focus

1. Пользователь бота без email открывает сайт через «Войти через Telegram» — тот же аккаунт, видит профили из бота. Тест в задаче 2.
2. Вход по почте для пользователя с `email=NULL` (кто-то вводит пустую почту) не находит/не создаёт его — 401/422, без 500. Тест в задаче 1.
3. Запрос бота с верным секретом и cookie чужой сессии — побеждает заголовок бота (детерминированно), cookie игнорируется. Тест в задаче 1.
4. Пользователь присылает боту файл не DOCX (фото, PDF при оформлении) — понятное сообщение, состояние не ломается. Тест в задаче 3.
5. Кнопки старого сообщения нажаты после перезапуска бота/истечения состояния — «Начните заново» и меню, без исключения. Тест в задаче 3.

---

### Task 1: Пользователь с Telegram ID и вход бота

**Files:** Create `backend/gostdoc_api/migrations/versions/0005_telegram.py`, `backend/gostdoc_api/bot_auth.py`, `backend/gostdoc_api/routes/config.py`, `backend/tests/api/test_bot_auth.py`; Modify `models.py` (User: `telegram_id` BigInteger unique nullable, `telegram_name` String(255) nullable, `email`/`password_hash` nullable), `config.py`, `auth.py` (`current_user`), `routes/profiles.py` (`_optional_user`), `guest.py` (`_owner`), `routes/auth.py` (`_user_out`, login), `app.py`, `Caddyfile`, `.env.example`.

**Interfaces:**
- `bot_auth.bot_user(request: Request, db: Session) -> User | None` — `None`, если заголовка `X-Bot-Secret` нет; `HTTPException(401, "Нужно войти")`, если секрет пуст/неверен или `X-Telegram-User` не положительное целое; иначе найденный/созданный пользователь (`telegram_name` из `X-Telegram-Name`, если передан).
- `current_user`, `_optional_user`, `guest._owner` сначала вызывают `bot_user`; при результате — это пользователь (гость не создаётся, cookie игнорируются).
- `_user_out(user) -> {"id", "email": str|None, "telegram_name": str|None, "telegram_linked": bool}`.
- `GET /config` → `{"telegram_bot_username": str|None}` (None, если нет токена).

- [ ] Тесты: автосоздание; повторный запрос — тот же id; неверный/пустой секрет → 401; `X-Telegram-User: abc`/`-1` → 401; бот создаёт задачу и видит только свои; **Review Focus 3**; **Review Focus 2** (логин с пустой почтой не 500); `/auth/me` для пользователя без email; `/config` с токеном и без; миграция 0005 вверх/вниз в существующем тесте миграций; Caddyfile содержит `request_header -X-Bot-Secret`, `-X-Telegram-User`, `-X-Telegram-Name` (тест читает файл).
- [ ] FAIL → реализация → `cd backend && python -m pytest -q && ruff check .`
- [ ] commit «Пользователь с Telegram ID, вход бота по секрету»

### Task 2: Вход и привязка через виджет Telegram (API)

**Files:** Create `backend/gostdoc_api/telegram_login.py`, `backend/tests/api/test_telegram_login.py`; Modify `routes/auth.py`, `docs/API.md`.

**Interfaces:**
- `telegram_login.verify(data: dict[str, str|int], bot_token: str, now: int) -> int` — возвращает `telegram_id` или бросает `TelegramAuthError`.
- `POST /auth/telegram` (тело — поля виджета) → сессия как при `login`, перенос гостевых задач (`claim_guest_jobs`), `telegram_name` = `first_name` + `last_name`; ответ — `_user_out`.
- `POST /auth/telegram/link` (UserDep) → ставит `telegram_id`; занят другим → 409.
- Нет токена → 503 «Функция не настроена».

- [ ] Тесты: верная подпись (считается в тесте по алгоритму из Global Constraints); подделанное поле → 401; `auth_date` старше суток → 401; новый пользователь создан и сессия-cookie выставлена; существующий найден; гостевые задачи перенесены; **Review Focus 1** (пользователь, созданный ботом по заголовкам, входит виджетом — тот же id и его профиль в списке); link успех и 409; 503 без токена.
- [ ] FAIL → реализация → весь `pytest`, `ruff`.
- [ ] commit «Вход и привязка через Telegram»

### Task 3: Каркас бота и оформление документа

**Files:** Create `backend/gostdoc_bot/{__init__,__main__,main,api,texts,keyboards,states}.py`, `backend/gostdoc_bot/handlers/{__init__,menu,format}.py`, `backend/tests/bot/test_format_flow.py`, `backend/tests/bot/conftest.py`; Modify `backend/pyproject.toml` (зависимость `aiogram>=3.13`, пакет `gostdoc_bot*`).

**Interfaces:**
- `api.ApiClient(base_url: str, secret: str, transport: httpx.AsyncBaseTransport | None = None)`; методы (все с `user_id: int, name: str | None`): `profiles()`, `create_job(file: tuple[str, bytes] | None, text: str | None, profile_id: str, mode: str) -> dict`, `job(id)`, `download(id, kind: "docx"|"pdf") -> bytes`, `jobs()`, `create_extraction(...)`, `extraction(id)`, `quota()`, `create_profile_from_extraction(id, accepted: list[int], name: str)`, `profile_json(id) -> bytes`, `config()`. Ошибка API → `ApiError(status, detail)`; сетевые → `ApiError(0, "Сервис временно недоступен, попробуйте позже")`.
- `main.build_dispatcher(api: ApiClient, storage: BaseStorage) -> Dispatcher` (для тестов с `MemoryStorage`); `main.run()` — `RedisStorage` с `state_ttl=data_ttl=3600`, polling; без токена — лог и выход 0.
- Меню и тексты — спецификация §4.2; `poll_job(...)` — опрос каждые 2 с, редактирует одно сообщение.

- [ ] Тесты (aiogram `Dispatcher.feed_update` с фейковым `Bot` через подменённую сессию; API через `httpx.MockTransport`): `/start` → меню из 5 кнопок; DOCX → кнопки профилей → режим → результат (сводка, ≤10 замечаний, отправлены 2 документа); текст из двух сообщений + «Готово» уходит одной строкой; ошибка лимита → текст `detail` + «В меню»; файл 21 МБ → «Файл больше 20 МБ»; **Review Focus 4** (фото/PDF при оформлении → «Пришлите DOCX-файл или вставьте текст сообщением»); **Review Focus 5** (callback без состояния → «Начните заново» + меню).
- [ ] FAIL → реализация → весь `pytest`, `ruff`.
- [ ] commit «Telegram-бот: меню и оформление документа»

### Task 4: Бот — профили, история, методичка

**Files:** Create `backend/gostdoc_bot/handlers/{profiles,history,guideline,help}.py`, `backend/tests/bot/test_profiles_history.py`, `backend/tests/bot/test_guideline_flow.py`.

**Interfaces:** Consumes `ApiClient` из задачи 3. Тексты и поведение — спецификация §4.2 («Мои профили», «История», «Создать профиль из методички», «Помощь»); по 8 строк на страницу, callback-данные ≤ 64 байт (`g:t:<idx>`, `g:p:<page>`, `g:ok`, `g:x`); пункт меню методички скрыт, если `config()`/quota отвечают 503.

- [ ] Тесты: профили — «Использовать» ведёт к шагу «пришлите документ» с выбранным профилем; «Скачать JSON» отправляет файл; история — 5 задач и кнопки скачивания только у готовых; методичка — 10 найденных → 2 страницы, переключение ✅/⬜ меняет `accepted`, «Создать профиль» → вопрос названия → «-» берёт имя файла → вызван `create_profile_from_extraction` с верными индексами → «Профиль создан»; функция выключена → кнопки нет.
- [ ] FAIL → реализация → весь `pytest`, `ruff`.
- [ ] commit «Telegram-бот: профили, история, профиль из методички»

### Task 5: Сайт — вход через Telegram, аккаунт, ссылка на бота

**Files:** Create `frontend/src/components/TelegramLogin.tsx` (+ тест), `frontend/src/app/account/page.tsx` (+ тест); Modify `frontend/src/lib/api.ts`, `useMe`, страницы `/login` и `/register`, шапка, главная.

**Interfaces:** `api.config() -> {telegram_bot_username}`, `api.telegramLogin(data)`, `api.telegramLink(data)`; `TelegramLogin({botUsername, onAuth})` вставляет `https://telegram.org/js/telegram-widget.js?22` с `data-telegram-login`, `data-size="large"`, `data-onauth`; поведение — спецификация §5.

- [ ] Vitest: кнопка не рендерится без `telegram_bot_username`; обработчик виджета зовёт `telegramLogin` и переходит по `next`; ошибка API показывается; шапка показывает `telegram_name` без email; `/account` — «Привязать Telegram» видна, если не привязан, 409 показывает текст; главная — ссылка `https://t.me/<username>`.
- [ ] `npm run lint && npm run typecheck && npm test && npm run build && PYTHON=/usr/bin/python3 npm run e2e`
- [ ] commit «Сайт: вход через Telegram, страница аккаунта»

### Task 6: Деплой

**Files:** Modify `docker-compose.yml` (сервис `bot`: образ бэкенда, `command: ["python","-m","gostdoc_bot"]`, env-якорь + `API_URL: http://api:8000`, `SITE_URL`; depends_on api(healthy)/redis(healthy); `restart: unless-stopped`, `init: true`; `api` получает новые переменные), `.env.example`, `DEPLOY.md`.

- [ ] DEPLOY.md, раздел «Telegram»: @BotFather → `/newbot` → токен в `.env`; `BOT_API_SECRET=$(openssl rand -hex 32)`; Tuna: установка, вход, постоянный поддомен на порт 80; `SITE_URL=https://<поддомен>`; `/setdomain` у @BotFather на поддомен; `COOKIE_SECURE=true`; запуск дома (Docker Desktop на Mac/Windows, отключить сон); что бот работает и без туннеля.
- [ ] `docker compose config` (с `POSTGRES_PASSWORD=x`) показывает `bot` и переменные у `api`; весь `pytest`.
- [ ] commit «Деплой: контейнер бота, туннель и Telegram в DEPLOY.md»
