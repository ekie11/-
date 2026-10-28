"""Клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def menu() -> InlineKeyboardMarkup:
    return _kb(
        [
            [_btn("Оформить документ", "menu:format")],
            [_btn("Мои профили", "menu:profiles")],
            [_btn("Создать профиль из методички", "menu:extract")],
            [_btn("История", "menu:history")],
            [_btn("Помощь", "menu:help")],
        ]
    )


def to_menu() -> InlineKeyboardMarkup:
    return _kb([[_btn("В меню", "menu:main")]])


def text_done() -> InlineKeyboardMarkup:
    return _kb([[_btn("Готово", "fdone")]])


def profiles(names: list[str]) -> InlineKeyboardMarkup:
    return _kb([[_btn(n, f"fp:{i}")] for i, n in enumerate(names)])


def modes() -> InlineKeyboardMarkup:
    return _kb(
        [
            [_btn("Проверить — оставим комментарии", "fm:check")],
            [_btn("Оформить — исправим сами", "fm:format")],
        ]
    )


def result(site_url: str, job_id: str) -> InlineKeyboardMarkup:
    rows = []
    if site_url:
        rows.append(
            [InlineKeyboardButton(text="Все замечания на сайте", url=f"{site_url}/jobs/{job_id}")]
        )
    rows.append([_btn("В меню", "menu:main")])
    return _kb(rows)
