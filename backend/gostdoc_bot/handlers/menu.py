"""Меню, помощь и ответ на кнопки без состояния."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import texts
from .common import Availability, main_menu

fallback = Router(name="fallback")


def build_routers():
    router = Router(name="router")
    fallback = Router(name="fallback")

    @router.message(CommandStart())
    @router.message(Command("menu"))
    async def start(message: Message, state: FSMContext, avail: Availability) -> None:
        await state.clear()
        await message.answer(texts.START, reply_markup=await main_menu(avail, message.from_user))

    @router.callback_query(F.data == "menu:main")
    async def to_main(cb: CallbackQuery, state: FSMContext, avail: Availability) -> None:
        await state.clear()
        await cb.answer()
        await cb.message.answer(texts.MENU, reply_markup=await main_menu(avail, cb.from_user))

    @fallback.callback_query()
    async def stale(cb: CallbackQuery, state: FSMContext, avail: Availability) -> None:
        """Кнопка старого сообщения: состояния нет или оно не подходит."""
        await state.clear()
        await cb.answer()
        if cb.message is not None:
            await cb.message.answer(
                texts.RESTART, reply_markup=await main_menu(avail, cb.from_user)
            )

    return router, fallback
