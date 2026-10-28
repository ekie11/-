"""Помощь."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import keyboards, texts


def build_router():
    router = Router(name="help")

    @router.callback_query(F.data == "menu:help")
    async def help_(cb: CallbackQuery, site_url: str = "") -> None:
        await cb.answer()
        text = texts.HELP
        if site_url:
            text += "\n\n" + texts.HELP_SITE.format(url=site_url)
        await cb.message.answer(text, reply_markup=keyboards.to_menu())

    return router
