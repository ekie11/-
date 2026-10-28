"""Меню, помощь и ответ на кнопки без состояния."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards, texts

fallback = Router(name="fallback")


def build_routers():
    router = Router(name="router")
    fallback = Router(name="fallback")

    @router.message(CommandStart())
    @router.message(Command("menu"))
    async def start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(texts.START, reply_markup=keyboards.menu())

    @router.callback_query(F.data == "menu:main")
    async def main_menu(cb: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cb.answer()
        await cb.message.answer(texts.MENU, reply_markup=keyboards.menu())

    @router.callback_query(F.data == "menu:help")
    async def help_(cb: CallbackQuery, site_url: str = "") -> None:
        await cb.answer()
        text = texts.HELP
        if site_url:
            text += "\n\n" + texts.HELP_SITE.format(url=site_url)
        await cb.message.answer(text, reply_markup=keyboards.to_menu())

    @router.callback_query(F.data.in_({"menu:profiles", "menu:extract", "menu:history"}))
    async def soon(cb: CallbackQuery) -> None:
        await cb.answer()
        await cb.message.answer(texts.SOON, reply_markup=keyboards.to_menu())

    @fallback.callback_query()
    async def stale(cb: CallbackQuery, state: FSMContext) -> None:
        """Кнопка старого сообщения: состояния нет или оно не подходит."""
        await state.clear()
        await cb.answer()
        if cb.message is not None:
            await cb.message.answer(texts.RESTART, reply_markup=keyboards.menu())

    return router, fallback
