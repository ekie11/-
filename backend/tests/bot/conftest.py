"""Фикстуры бота: фейковая сессия Telegram и API на httpx.MockTransport."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from itertools import count

import httpx
import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    GetFile,
    SendDocument,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    Document,
    File,
    Message,
    PhotoSize,
    Update,
    User,
)

from gostdoc_bot.api import ApiClient
from gostdoc_bot.main import build_dispatcher

USER = User(id=42, is_bot=False, first_name="Иван", last_name="Петров")
CHAT = Chat(id=42, type="private")


class FakeSession(BaseSession):
    """Записывает вызовы Bot API и возвращает правдоподобные ответы."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []
        self.files: dict[str, bytes] = {}
        self._ids = count(1000)

    async def close(self) -> None:  # pragma: no cover
        pass

    def _message(self, bot, text: str | None = None) -> Message:
        msg = Message(message_id=next(self._ids), date=datetime.now(UTC), chat=CHAT, text=text)
        return msg.as_(bot)

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage | EditMessageText):
            return self._message(bot, method.text)
        if isinstance(method, SendDocument):
            return self._message(bot)
        if isinstance(method, AnswerCallbackQuery):
            return True
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_path=method.file_id)
        return True

    async def stream_content(
        self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True
    ):
        yield self.files[url.rsplit("/", 1)[-1]]

    def of(self, kind):
        return [c for c in self.calls if isinstance(c, kind)]

    def texts(self) -> list[str]:
        out = []
        for c in self.calls:
            if isinstance(c, SendMessage | EditMessageText):
                out.append(c.text)
        return out

    def last_markup(self):
        for c in reversed(self.calls):
            if isinstance(c, SendMessage | EditMessageText) and c.reply_markup:
                return c.reply_markup
        return None

    def button_texts(self) -> list[str]:
        m = self.last_markup()
        return [b.text for row in m.inline_keyboard for b in row] if m else []

    def callback_for(self, text: str) -> str:
        for row in self.last_markup().inline_keyboard:
            for b in row:
                if b.text == text:
                    return b.callback_data
        raise AssertionError(f"нет кнопки {text!r}: {self.button_texts()}")


class FakeApi:
    """Сценарий ответов API; запросы записываются в .requests."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.profiles = [
            {"id": "gost-7.32", "name": "ГОСТ 7.32-2017", "base": None, "readonly": True},
            {"id": "p1", "name": "Мой профиль", "base": "gost-7.32", "readonly": False},
        ]
        self.job_statuses = ["running", "done"]
        self.report = {
            "issues": [
                {"rule": "page.margins", "message": f"Замечание {i}", "severity": "error"}
                for i in range(12)
            ],
            "summary": {"errors": 12, "recommendations": 0},
        }
        self.error: tuple[int, str] | None = None
        self.has_pdf = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/jobs" and request.method == "POST":
            if self.error:
                return httpx.Response(self.error[0], json={"detail": self.error[1]})
            return httpx.Response(202, json={"id": "j1", "status": "queued"})
        if path == "/profiles":
            return httpx.Response(200, json=self.profiles)
        if path == "/jobs/j1":
            status = (
                self.job_statuses.pop(0) if len(self.job_statuses) > 1 else self.job_statuses[0]
            )
            body = {
                "id": "j1",
                "status": status,
                "mode": "format",
                "error": None,
                "has_pdf": self.has_pdf,
                "report": self.report if status == "done" else None,
            }
            return httpx.Response(200, json=body)
        if path == "/jobs/j1/docx":
            return httpx.Response(200, content=b"DOCX-RESULT")
        if path == "/jobs/j1/pdf":
            return httpx.Response(200, content=b"PDF-RESULT")
        return httpx.Response(404, json={"detail": "нет"})

    def client(self) -> ApiClient:
        return ApiClient("http://api", "s3cret", transport=httpx.MockTransport(self.handler))


class BotHarness:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.bot = Bot("123:TEST", session=self.session)
        self.fake_api = FakeApi()
        self.dp = build_dispatcher(
            self.fake_api.client(),
            MemoryStorage(),
            poll_interval=0.001,
            site_url="https://site.test",
        )
        self._uid = count(1)

    def feed(self, update: Update) -> None:
        asyncio.run(self.dp.feed_update(self.bot, update))

    def _msg(self, **kw) -> Message:
        return Message(
            message_id=next(self._uid), date=datetime.now(UTC), chat=CHAT, from_user=USER, **kw
        )

    def say(self, text: str) -> None:
        self.feed(Update(update_id=next(self._uid), message=self._msg(text=text)))

    def send_document(self, name: str, data: bytes, size: int | None = None) -> None:
        fid = f"f{next(self._uid)}"
        self.session.files[fid] = data
        doc = Document(
            file_id=fid,
            file_unique_id=fid,
            file_name=name,
            file_size=len(data) if size is None else size,
        )
        self.feed(Update(update_id=next(self._uid), message=self._msg(document=doc)))

    def send_photo(self) -> None:
        photo = [PhotoSize(file_id="p", file_unique_id="p", width=1, height=1)]
        self.feed(Update(update_id=next(self._uid), message=self._msg(photo=photo)))

    def press(self, data: str) -> None:
        msg = Message(message_id=1, date=datetime.now(UTC), chat=CHAT, text="старое")
        cq = CallbackQuery(
            id=str(next(self._uid)), from_user=USER, chat_instance="c", message=msg, data=data
        )
        self.feed(Update(update_id=next(self._uid), callback_query=cq))

    def press_button(self, text: str) -> None:
        self.press(self.session.callback_for(text))


@pytest.fixture
def bot():
    return BotHarness()


def multipart_fields(request: httpx.Request) -> dict[str, bytes]:
    """Грубый разбор multipart: имя поля -> тело."""
    ctype = request.headers["content-type"]
    if "boundary=" not in ctype:  # без файла httpx шлёт urlencoded
        from urllib.parse import parse_qsl

        return {k: v.encode() for k, v in parse_qsl(request.content.decode())}
    boundary = ctype.split("boundary=")[1].encode()
    out = {}
    for part in request.content.split(b"--" + boundary)[1:-1]:
        head, _, body = part.partition(b"\r\n\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        out[name] = body.removesuffix(b"\r\n")
    return out
