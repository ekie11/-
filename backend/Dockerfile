# Один образ для api, worker, cleanup и migrate (команда задаётся в compose).
# Контекст сборки — корень репозитория: docker build -f backend/Dockerfile .
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# LibreOffice нужен только для PDF-предпросмотра и номеров страниц оглавления.
# python3-uno ставится под системный python Debian (/usr/bin/python3, 3.11),
# а приложение работает на python образа (3.12): поэтому LO_PYTHON указывает на системный.
# Шрифты: Liberation метрически совместим с Times New Roman/Arial/Courier New.
# ttf-mscorefonts-installer НЕЛЬЗЯ: он требует принять EULA Microsoft.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer-nogui python3-uno \
        fonts-liberation fonts-dejavu-core fontconfig tini \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

ENV LO_PYTHON=/usr/bin/python3 SOFFICE_PATH=soffice STORAGE_DIR=/data/storage

WORKDIR /app
COPY backend/ /app/backend/
# Редактируемая установка обязательна: профили ищутся рядом с пакетом (backend/profiles).
RUN pip install -e /app/backend

RUN useradd --create-home --uid 1000 app && mkdir -p /data/storage && chown -R app:app /data
USER app
WORKDIR /app/backend

EXPOSE 8000
CMD ["python", "-m", "gostdoc_api", "serve", "--host", "0.0.0.0", "--port", "8000"]
