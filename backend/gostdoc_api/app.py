"""Фабрика FastAPI-приложения."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings, get_settings
from .db import make_engine, make_sessionmaker
from .routes import auth as auth_routes
from .routes import jobs as jobs_routes
from .routes import profiles as profiles_routes

log = logging.getLogger(__name__)

GENERIC_INVALID = "Неверные данные запроса"
FORM_INVALID = "Неверные данные формы"
TOO_BIG = "Файл слишком большой — максимум 20 МБ"
MAX_BODY = 21 * 1024 * 1024  # 20 МБ файла + запас на multipart-обвязку
DRAIN_MAX_BYTES = 32 * 1024 * 1024  # сколько всего читаем из тела перед отказом
DRAIN_MAX_SECONDS = 10.0
_CYRILLIC = re.compile("[а-яёА-ЯЁ]")


class _BodyTooLarge(BaseException):  # BaseException: FastAPI не должен превращать её в 400
    pass


class BodyLimitMiddleware:
    """Отсекает слишком большие тела запроса до разбора multipart."""

    def __init__(self, app: ASGIApp, max_body: int = MAX_BODY) -> None:
        self.app = app
        self.max_body = max_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    too_big = int(value) > self.max_body
                except ValueError:
                    too_big = False
                if too_big:
                    await self._reject(scope, receive, send, 0)
                    return
        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            if started:
                raise
            await self._reject(scope, receive, send, received)

    async def _drain(self, receive: Receive, received: int) -> None:
        """Дочитывает и выбрасывает тело, чтобы клиент не получил ECONNRESET при записи."""
        deadline = time.monotonic() + DRAIN_MAX_SECONDS
        try:
            while received < DRAIN_MAX_BYTES:
                left = deadline - time.monotonic()
                if left <= 0:
                    return
                message = await asyncio.wait_for(receive(), timeout=left)
                if message["type"] != "http.request":
                    return
                received += len(message.get("body", b""))
                if not message.get("more_body", False):
                    return
        except (TimeoutError, OSError):
            return

    async def _reject(self, scope: Scope, receive: Receive, send: Send, received: int) -> None:
        await self._drain(receive, received)
        response = JSONResponse(status_code=413, content={"detail": TOO_BIG})
        await response(scope, receive, send)


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
    if "DATABASE_URL" not in os.environ:
        log.warning(
            "DATABASE_URL не задан — используется %s (допустимо только для разработки)",
            settings.database_url,
        )
    app = FastAPI(title="GostDoc API")
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)

    app.add_middleware(BodyLimitMiddleware)

    app.include_router(auth_routes.router)
    app.include_router(profiles_routes.router)
    app.include_router(profiles_routes.fields_router)
    app.include_router(jobs_routes.router)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=400, content={"detail": _validation_message(request, exc)})

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException):
        # Ошибки разбора multipart приходят от Starlette по-английски
        if exc.status_code == 400 and not _CYRILLIC.search(str(exc.detail)):
            return JSONResponse(status_code=400, content={"detail": FORM_INVALID})
        return await http_exception_handler(request, exc)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
