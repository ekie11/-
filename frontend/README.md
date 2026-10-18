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
