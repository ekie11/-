"""Мои профили: список, «Использовать», «Скачать JSON»."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .. import keyboards, texts
from ..api import UNAVAILABLE, ApiClient, ApiError
from . import format as format_flow
from .common import Availability, fail, main_menu, reply, who

PAGE = 8


async def show_page(target: Message, user, api: ApiClient, page: int, site_url: str) -> None:
    uid, name = who(user)
    try:
        own = [p for p in await api.profiles(uid, name) if not p.get("readonly")]
    except ApiError as exc:
        return await fail(target, exc)
    if not own:
        return await target.answer(texts.NO_OWN_PROFILES, reply_markup=keyboards.to_menu())
    pages = (len(own) + PAGE - 1) // PAGE
    page = min(max(page, 0), pages - 1)
    for p in own[page * PAGE : (page + 1) * PAGE]:
        await target.answer(p["name"], reply_markup=keyboards.profile_actions(p["id"], site_url))
    if pages > 1:
        await target.answer(
            texts.PROFILES_HEAD.format(page=page + 1, pages=pages),
            reply_markup=keyboards.profiles_pager(page, pages),
        )


def build_router():
    router = Router(name="profiles")

    @router.callback_query(F.data == "menu:profiles")
    async def open_list(
        cb: CallbackQuery, state: FSMContext, api: ApiClient, site_url: str = ""
    ) -> None:
        await cb.answer()
        await state.clear()
        await show_page(cb.message, cb.from_user, api, 0, site_url)

    @router.callback_query(F.data.regexp(r"^pp:\d+$"))
    async def other_page(cb: CallbackQuery, api: ApiClient, site_url: str = "") -> None:
        await cb.answer()
        await show_page(cb.message, cb.from_user, api, int(cb.data.split(":")[1]), site_url)

    @router.callback_query(F.data.startswith("pu:"))
    async def use(
        cb: CallbackQuery, state: FSMContext, api: ApiClient, avail: Availability
    ) -> None:
        await cb.answer()
        pid = cb.data[3:]
        uid, name = who(cb.from_user)
        try:
            profiles = await api.profiles(uid, name)
        except ApiError as exc:
            return await fail(cb.message, exc)
        found = next((p for p in profiles if p["id"] == pid), None)
        if found is None:
            await state.clear()
            return await cb.message.answer(
                texts.RESTART, reply_markup=await main_menu(avail, cb.from_user)
            )
        await format_flow.start_flow(cb.message, state, pid, found["name"])

    @router.callback_query(F.data.startswith("pj:"))
    async def download_json(cb: CallbackQuery, api: ApiClient) -> None:
        await cb.answer()
        pid = cb.data[3:]
        uid, name = who(cb.from_user)
        try:
            data = await api.profile_json(uid, name, pid)
            await cb.message.answer_document(BufferedInputFile(data, f"{pid}.json"))
        except ApiError as exc:
            await reply(cb.message, exc.detail)
        except TelegramAPIError:
            await reply(cb.message, UNAVAILABLE)

    return router
