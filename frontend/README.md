# Фронтенд ГОСТ-сервиса

Next.js (App Router), TypeScript, Tailwind 4. Без UI-библиотек.

```bash
npm install
npm run dev        # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build
```

Запросы идут на `/api/...`; `next.config.ts` проксирует их на `API_URL`
(по умолчанию `http://127.0.0.1:8000`), то есть в бэкенд без префикса `/api`.

Загрузка файлов: rewrites-прокси Next 16 не буферизует тело запроса для
маршрутов без middleware/proxy-файла, поэтому ограничение на размер задаёт
бэкенд (21 МБ). Дополнительных настроек Next не потребовалось. В продакшене
ограничьте тело и на обратном прокси.

## Запуск вместе с API

```bash
# терминал 1: Redis, API и воркер (из каталога backend)
redis-server &
python -m gostdoc_api migrate && python -m gostdoc_api serve &
python -m gostdoc_api worker
# терминал 2
npm run dev
```

Для HTTP без TLS задайте `COOKIE_SECURE=false` у API.

## Сквозные тесты

```bash
npm run e2e   # Playwright, Chromium
```

`e2e/start-stack.sh` сам поднимает Redis (нужен `redis-server`), API и воркер
с временной SQLite и фиктивным `soffice`; Next собирается и стартует на :3000.
Переменные: `PYTHON` (интерпретатор с установленным `backend[dev]`),
`PW_CHROMIUM` (путь к своему Chromium вместо скачанного Playwright).
Браузер ставится командой `npx playwright install chromium`.
