"""Оформление документа: файл или текст -> профиль -> режим -> результат."""

from __future__ import annotations

import asyncio
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .. import keyboards, texts
from ..api import UNAVAILABLE, ApiClient, ApiError
from ..states import FormatFlow

MAX_FILE = 20 * 1024 * 1024
MAX_WAIT_S = 300
SHOWN_ISSUES = 10
ISSUE_CHARS = 300
POLL_RETRIES = 3


def _who(user) -> tuple[int, str | None]:
    return user.id, (user.full_name or None)


async def _reply(target: Message, text: str) -> None:
    """Ответ с кнопкой «В меню»; сбой самого Telegram не должен ронять обработчик."""
    try:
        await target.answer(text, reply_markup=keyboards.to_menu())
    except TelegramAPIError:
        pass


async def _fail(target: Message, exc: ApiError, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await target.answer(exc.detail, reply_markup=keyboards.to_menu())


async def _ask_profile(message: Message, user, state: FSMContext, api: ApiClient) -> None:
    uid, name = _who(user)
    try:
        profiles = await api.profiles(uid, name)
    except ApiError as exc:
        return await _fail(message, exc, state)
    if not profiles:
        await state.clear()
        return await message.answer(texts.NO_PROFILES, reply_markup=keyboards.to_menu())
    await state.update_data(profile_ids=[p["id"] for p in profiles])
    await state.set_state(FormatFlow.choosing_profile)
    await message.answer(
        texts.CHOOSE_PROFILE, reply_markup=keyboards.profiles([p["name"] for p in profiles])
    )


async def _finish_text(message: Message, user, state: FSMContext, api: ApiClient) -> None:
    if not (await state.get_data()).get("parts"):
        return await message.answer(texts.SEND_DOC)
    await _ask_profile(message, user, state, api)


async def poll_job(
    status: Message, api: ApiClient, uid: int, name: str | None, job_id: str, interval: float
) -> dict | None:
    """Опрашивает задачу, редактируя одно сообщение; None — не дождались."""
    shown = texts.QUEUED
    deadline = time.monotonic() + MAX_WAIT_S
    failures = 0
    while time.monotonic() < deadline:
        try:
            job = await api.job(uid, name, job_id)
            failures = 0
        except ApiError as exc:
            failures += 1
            if (exc.status != 0 and exc.status < 500) or failures >= POLL_RETRIES:
                raise
            await asyncio.sleep(interval)
            continue
        if job["status"] in ("done", "error", "expired"):
            return job
        label = texts.PROCESSING if job["status"] == "running" else texts.QUEUED
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


async def send_result(
    message: Message,
    api: ApiClient,
    uid: int,
    name: str | None,
    job: dict,
    mode: str,
    site_url: str,
) -> None:
    report = job.get("report") or {}
    lines = [texts.summary(report, mode)]
    issues = report.get("issues") or []
    if issues:
        lines.append(texts.ISSUES_HEAD.format(n=min(len(issues), SHOWN_ISSUES)))
        lines += [
            f"{i}. {str(it.get('message', ''))[:ISSUE_CHARS]}"
            for i, it in enumerate(issues[:SHOWN_ISSUES], 1)
        ]
    try:
        await message.answer("\n".join(lines), reply_markup=keyboards.result(site_url, job["id"]))
        docx = await api.download(uid, name, job["id"], "docx")
        await message.answer_document(BufferedInputFile(docx, "result.docx"))
        if job.get("has_pdf"):
            pdf = await api.download(uid, name, job["id"], "pdf")
            await message.answer_document(BufferedInputFile(pdf, "result.pdf"))
    except ApiError as exc:
        await _reply(message, exc.detail or texts.FILES_FAILED)
    except TelegramAPIError:
        await _reply(message, UNAVAILABLE)


def build_router():
    router = Router(name="router")

    @router.callback_query(F.data == "menu:format")
    async def begin(cb: CallbackQuery, state: FSMContext) -> None:
        await cb.answer()
        await state.clear()
        await state.set_state(FormatFlow.waiting_input)
        await state.update_data(parts=[], file_id=None)
        await cb.message.answer(texts.SEND_DOC)

    @router.message(StateFilter(FormatFlow.waiting_input), F.document)
    async def got_document(message: Message, state: FSMContext, api: ApiClient) -> None:
        doc = message.document
        if (doc.file_size or 0) > MAX_FILE:
            return await message.answer(texts.FILE_TOO_BIG, reply_markup=keyboards.to_menu())
        if not (doc.file_name or "").lower().endswith(".docx"):
            return await message.answer(texts.SEND_DOC)
        await state.update_data(file_id=doc.file_id, parts=[])
        await _ask_profile(message, message.from_user, state, api)

    @router.message(StateFilter(FormatFlow.waiting_input), F.text.casefold() == "готово")
    async def text_done(message: Message, state: FSMContext, api: ApiClient) -> None:
        await _finish_text(message, message.from_user, state, api)

    @router.callback_query(StateFilter(FormatFlow.waiting_input), F.data == "fdone")
    async def text_done_button(cb: CallbackQuery, state: FSMContext, api: ApiClient) -> None:
        await cb.answer()
        await _finish_text(cb.message, cb.from_user, state, api)

    @router.message(StateFilter(FormatFlow.waiting_input), F.text, ~F.text.startswith("/"))
    async def got_text(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        parts = [*data.get("parts", []), message.text]
        await state.update_data(parts=parts, file_id=None)
        total = sum(len(p) for p in parts)
        await message.answer(
            texts.TEXT_ACCEPTED.format(n=total), reply_markup=keyboards.text_done()
        )

    @router.message(StateFilter(FormatFlow.waiting_input))
    async def wrong_input(message: Message) -> None:
        await message.answer(texts.SEND_DOC)

    @router.callback_query(StateFilter(FormatFlow.choosing_profile), F.data.regexp(r"^fp:\d+$"))
    async def chose_profile(cb: CallbackQuery, state: FSMContext) -> None:
        await cb.answer()
        ids = (await state.get_data()).get("profile_ids", [])
        idx = int(cb.data.split(":")[1])
        if idx >= len(ids):
            await state.clear()
            return await cb.message.answer(texts.RESTART, reply_markup=keyboards.menu())
        await state.update_data(profile_id=ids[idx])
        await state.set_state(FormatFlow.choosing_mode)
        await cb.message.answer(texts.CHOOSE_MODE, reply_markup=keyboards.modes())

    @router.callback_query(
        StateFilter(FormatFlow.choosing_mode), F.data.in_({"fm:check", "fm:format"})
    )
    async def chose_mode(
        cb: CallbackQuery,
        state: FSMContext,
        bot: Bot,
        api: ApiClient,
        poll_interval: float = 2.0,
        site_url: str = "",
    ) -> None:
        await cb.answer()
        mode = cb.data.split(":")[1]
        data = await state.get_data()
        uid, name = _who(cb.from_user)
        try:
            status = await cb.message.answer(texts.QUEUED)
            file = None
            text = None
            if data.get("file_id"):
                tg_file = await bot.get_file(data["file_id"])
                buf = await bot.download_file(tg_file.file_path)
                file = ("input.docx", buf.read())
            else:
                text = "\n".join(data.get("parts", []))
            job = await api.create_job(uid, name, file, text, data["profile_id"], mode)
        except ApiError as exc:  # состояние сохраняем: можно выбрать режим ещё раз
            return await _reply(cb.message, exc.detail)
        except TelegramAPIError as exc:
            too_big = "too big" in str(exc).lower()
            return await _reply(cb.message, texts.FILE_TOO_BIG if too_big else UNAVAILABLE)
        await state.clear()
        try:
            final = await poll_job(status, api, uid, name, job["id"], poll_interval)
        except ApiError as exc:
            return await _reply(cb.message, exc.detail)
        if final is None:
            return await _reply(cb.message, texts.JOB_TIMEOUT)
        if final["status"] == "error":
            return await _reply(cb.message, final.get("error") or texts.JOB_FAILED)
        if final["status"] == "expired":
            return await _reply(cb.message, texts.JOB_EXPIRED)
        await send_result(cb.message, api, uid, name, final, mode, site_url)

    return router
