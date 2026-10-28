"""История: пять последних задач и скачивание готовых файлов."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from .. import keyboards, texts
from ..api import UNAVAILABLE, ApiClient, ApiError
from .common import fail, reply, who

SHOWN = 5


def _when(iso: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def _line(job: dict) -> str:
    created = _when(job.get("created_at"))
    date = created.strftime("%d.%m.%Y %H:%M") if created else "—"
    mode = texts.MODE_NAMES.get(job.get("mode"), job.get("mode") or "—")
    status = texts.STATUS_NAMES.get(job.get("status"), job.get("status") or "—")
    return f"{date} · {job.get('profile_name') or '—'} · {mode} · {status}"


def _downloadable(job: dict) -> bool:
    if job.get("status") != "done":
        return False
    expires = _when(job.get("expires_at"))
    if expires is not None:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires > datetime.now(UTC)
    return True


def build_router():
    router = Router(name="history")

    @router.callback_query(F.data == "menu:history")
    async def show(
        cb: CallbackQuery, state: FSMContext, api: ApiClient, site_url: str = ""
    ) -> None:
        await cb.answer()
        await state.clear()
        uid, name = who(cb.from_user)
        try:
            jobs = (await api.jobs(uid, name))[:SHOWN]
        except ApiError as exc:
            return await fail(cb.message, exc)
        if not jobs:
            return await cb.message.answer(texts.NO_HISTORY, reply_markup=keyboards.to_menu())
        await cb.message.answer(texts.HISTORY_HEAD)
        for job in jobs:
            await cb.message.answer(
                _line(job),
                reply_markup=keyboards.job_actions(job["id"], site_url, _downloadable(job)),
            )
        await cb.message.answer(texts.MENU, reply_markup=keyboards.to_menu())

    @router.callback_query(F.data.regexp(r"^h[dp]:"))
    async def download(cb: CallbackQuery, api: ApiClient) -> None:
        await cb.answer()
        kind = "docx" if cb.data[1] == "d" else "pdf"
        job_id = cb.data[3:]
        uid, name = who(cb.from_user)
        try:
            data = await api.download(uid, name, job_id, kind)
            await cb.message.answer_document(BufferedInputFile(data, f"result.{kind}"))
        except ApiError as exc:
            await reply(cb.message, exc.detail or texts.FILE_FAILED)
        except TelegramAPIError:
            await reply(cb.message, UNAVAILABLE)

    return router
