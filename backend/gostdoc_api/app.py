"""Фабрика FastAPI-приложения."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .db import make_engine, make_sessionmaker
from .routes import auth as auth_routes
from .routes import jobs as jobs_routes
from .routes import profiles as profiles_routes

GENERIC_INVALID = "Неверные данные запроса"


def _validation_message(request: Request, exc: RequestValidationError) -> str:
    if request.url.path == "/auth/register":
        for err in exc.errors():
            loc = err.get("loc", ())
            if "email" in loc:
                return "Неверный email"
            if "password" in loc:
                return "Пароль должен быть не короче 8 символов"
    return GENERIC_INVALID


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="GostDoc API")
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)

    app.include_router(auth_routes.router)
    app.include_router(profiles_routes.router)
    app.include_router(jobs_routes.router)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=400, content={"detail": _validation_message(request, exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
