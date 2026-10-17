"""Фабрика FastAPI-приложения."""

from __future__ import annotations

from fastapi import FastAPI

from .config import Settings, get_settings
from .db import make_engine, make_sessionmaker


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="GostDoc API")
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
