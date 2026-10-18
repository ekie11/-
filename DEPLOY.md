# Развёртывание на VPS (Docker Compose)

Всё работает в контейнерах: Postgres, Redis, API, воркер, фронтенд и Caddy
(единственная точка входа, порты 80 и 443). Пока домена нет, сайт открывается
по HTTP на IP сервера; переход на домен с автоматическим HTTPS — одна строка.

---

## Что делаете вы, а что уже готово

Готово в репозитории: `backend/Dockerfile`, `frontend/Dockerfile`,
`docker-compose.yml`, `Caddyfile`, `.env.example`, `.github/workflows/docker.yml`
(проверочная сборка образов на PR).

Нужны ваши учётные данные и сервер, поэтому эти шаги за вами.

## 1. Арендовать сервер

VPS: 2 vCPU, 2–4 ГБ RAM, 20 ГБ диска, Ubuntu 24.04. Подойдут Timeweb Cloud,
Selectel, Yandex Cloud. LibreOffice при конвертации в PDF занимает до ~1 ГБ,
так что 1 ГБ RAM мало.

## 2. Установить Docker

```bash
ssh root@IP_СЕРВЕРА
curl -fsSL https://get.docker.com | sh
```

## 3. Файрвол

```bash
ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw enable
```

Порты Postgres и Redis наружу не публикуются. Внимание: Docker обходит ufw для
опубликованных портов, поэтому в compose наружу открыты только 80 и 443 у Caddy.

## 4. Забрать код и настроить

```bash
git clone URL_РЕПОЗИТОРИЯ gostdoc && cd gostdoc
git checkout claude/elegant-knuth-30660g   # или main после слияния
cp .env.example .env
nano .env     # заменить POSTGRES_PASSWORD (openssl rand -hex 24)
```

## 5. Запустить

```bash
docker compose up -d --build
docker compose ps
```

Первая сборка занимает 5–10 минут (LibreOffice тяжёлый). Откройте
`http://IP_СЕРВЕРА/`. Проверка API: `curl http://IP_СЕРВЕРА/api/health`.

Порядок старта: postgres -> migrate (миграции БД, одноразово) -> api, worker,
extract-worker, cleanup -> frontend -> caddy. Общий том `storage` смонтирован в api и worker.
Контейнер `cleanup` раз в сутки удаляет просроченные файлы и гостевые сессии.

---

## Важно: пока HTTP

Без домена трафик не шифруется: пароли и документы идут открытым текстом.
Не используйте здесь пароли, которые вы применяете где-то ещё, и не загружайте
чувствительные документы. Домен стоит завести как можно раньше.
`COOKIE_SECURE=false` нужен только на этом этапе (иначе браузер не сохранит cookie
сессии по HTTP).

## Переход на домен

1. DNS: A-запись `example.ru` -> IP сервера (дождитесь обновления DNS).
2. `Caddyfile`: удалить блок `:80 { ... }`, раскомментировать блок `example.ru { ... }`
   и вписать свой домен.
3. `.env`: `COOKIE_SECURE=true`.
4. `docker compose up -d` (контейнеры пересоздадутся, Caddy сам выпустит сертификат;
   порты 80 и 443 должны быть открыты).

## Клиентские IP и TRUSTED_PROXIES

Caddy ставит `X-Forwarded-For` с адресом клиента, Next.js пробрасывает заголовок
в API как есть, а сам API видит подключение от контейнера frontend. Поэтому
`TRUSTED_PROXIES=172.28.0.0/16` — подсеть compose (она закреплена в
`docker-compose.yml`). Если менять подсеть, поменяйте оба места. Без этой
настройки все гости получат один IP.

## Обновление

```bash
cd gostdoc && git pull && docker compose up -d --build
```

Миграции применятся автоматически (сервис `migrate`).

## Бэкапы

```bash
# база
docker compose exec -T postgres pg_dump -U gostdoc gostdoc | gzip > backup-$(date +%F).sql.gz
# файлы задач (том storage)
docker run --rm -v gostdoc_storage:/s -v "$PWD":/b alpine tar czf /b/storage-$(date +%F).tgz -C /s .
```

Восстановление БД: `gunzip -c backup.sql.gz | docker compose exec -T postgres psql -U gostdoc gostdoc`.
Файлы задач живут `FILE_TTL_DAYS` дней, их бэкап необязателен.

## ИИ: профиль из методички

Функция «загрузить методичку и получить профиль» использует внешнюю модель.

1. Получите ключ в консоли Zhipu (bigmodel.cn): регистрация, раздел API Keys.
2. Впишите ключ только в `.env` на сервере (`LLM_API_KEY=...`). Не коммитьте его в git и не присылайте в чат.
3. Переменные (значения по умолчанию в `.env.example`): `LLM_BASE_URL`, `LLM_MODEL`,
   `LLM_TIMEOUT_S` (таймаут запроса, с), `EXTRACT_USER_DAILY` (разборов в сутки на
   пользователя, по умолчанию 5), `EXTRACT_GLOBAL_DAILY` (всего в сутки, по умолчанию 500).
4. Модель: по умолчанию бесплатная `glm-4.5-flash` (у неё лимит 2 параллельных запроса на ключ).
   Платные альтернативы: `glm-4.6` или Yandex через `LLM_BASE_URL`/`LLM_MODEL`.
   Извлечения идут в отдельную очередь `extractions`, её обслуживает сервис `extract-worker`
   ровно в один процесс (не масштабируйте его), при ответе 429 запрос повторяется с паузами 5/15/30 с.
5. Во внешний сервис в Китае уходит только текст методички, документы студентов никогда.
6. Миграции применяются как обычно (`docker compose up -d --build`, миграция 0003).
7. Пока `LLM_API_KEY` пуст, функция скрыта. После правки `.env`: `docker compose up -d`.

## Логи и диагностика

```bash
docker compose logs -f api worker extract-worker
docker compose ps
docker compose restart worker
```

## Заметки

- Шрифты: Times New Roman не ставится (лицензия Microsoft, `ttf-mscorefonts-installer`
  требует принять EULA), вместо него `fonts-liberation`: он метрически совместим,
  номера страниц в оглавлении совпадут.
- `API_URL` для фронтенда зашит при сборке образа (`http://api:8000`, Next.js
  фиксирует rewrites на build). Менять имя сервиса api без пересборки нельзя.
- Лимит тела запроса 22 МБ задан в Caddy и в Next, API отклоняет всё больше 21 МБ.
