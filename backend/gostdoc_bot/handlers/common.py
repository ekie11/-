"""Общие помощники обработчиков: ошибки, опрос, загрузка файла, доступность функций."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message

from .. import keyboards
from ..api import ApiClient, ApiError

MAX_FILE = 20 * 1024 * 1024
MAX_WAIT_S = 300
POLL_RETRIES = 3
FINAL_STATUSES = ("done", "error", "failed", "expired")
AVAILABILITY_TTL_S = 300


def who(user) -> tuple[int, str | None]:
    return user.id, (user.full_name or None)


async def reply(target: Message, text: str) -> None:
    """Ответ с кнопкой «В меню»; сбой самого Telegram не должен ронять обработчик."""
    try:
        await target.answer(text, reply_markup=keyboards.to_menu())
    except TelegramAPIError:
        pass


async def fail(target: Message, exc: ApiError, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await target.answer(exc.detail, reply_markup=keyboards.to_menu())


async def drop(message: Message | None) -> None:
    """Убирает устаревшее служебное сообщение («В очереди…»); ошибки не важны."""
    if message is None:
        return
    try:
        await message.delete()
    except TelegramAPIError:
        pass


async def download_file(bot: Bot, file_id: str, name: str) -> tuple[str, bytes]:
    tg_file = await bot.get_file(file_id)
    buf = await bot.download_file(tg_file.file_path)
    return name, buf.read()


def too_big(exc: TelegramAPIError) -> bool:
    return "too big" in str(exc).lower()


async def poll(
    status: Message,
    fetch: Callable[[], Awaitable[dict]],
    labels: dict[str, str],
    interval: float,
) -> dict | None:
    """Опрашивает задачу, редактируя одно сообщение; None — не дождались."""
    shown = labels["queued"]
    deadline = time.monotonic() + MAX_WAIT_S
    failures = 0
    while time.monotonic() < deadline:
        try:
            job = await fetch()
            failures = 0
        except ApiError as exc:
            failures += 1
            if (exc.status != 0 and exc.status < 500) or failures >= POLL_RETRIES:
                raise
            await asyncio.sleep(interval)
            continue
        if job["status"] in FINAL_STATUSES:
            return job
        label = labels.get(job["status"], labels["queued"])
        if label != shown:
            try:
                await status.edit_text(label)
            except TelegramBadRequest:
                pass  # «message is not modified» и подобное
            except TelegramAPIError:
                pass
            shown = label
        await asyncio.sleep(interval)
    return None


class Availability:
    """Включена ли «профиль из методички»: 503 от /extractions/quota = выключена.

    Ответ держим несколько минут в памяти процесса; при сбое сети кнопку показываем
    и результат не запоминаем.
    """

    def __init__(
        self,
        api: ApiClient,
        ttl: float = AVAILABILITY_TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api = api
        self._ttl = ttl
        self._clock = clock
        self._value: bool | None = None
        self._until = 0.0

    async def extraction(self, user) -> bool:
        if self._value is not None and self._clock() < self._until:
            return self._value
        uid, name = who(user)
        try:
            await self._api.quota(uid, name)
            value = True
        except ApiError as exc:
            if exc.status != 503:
                return True
            value = False
        self._value, self._until = value, self._clock() + self._ttl
        return value


async def main_menu(avail: Availability, user) -> InlineKeyboardMarkup:
    return keyboards.menu(extract=await avail.extraction(user))
