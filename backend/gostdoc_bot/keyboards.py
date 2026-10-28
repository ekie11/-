"""Клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def menu(extract: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [_btn("Оформить документ", "menu:format")],
        [_btn("Мои профили", "menu:profiles")],
    ]
    if extract:
        rows.append([_btn("Создать профиль из методички", "menu:extract")])
    rows += [[_btn("История", "menu:history")], [_btn("Помощь", "menu:help")]]
    return _kb(rows)


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


def profile_actions(profile_id: str, site_url: str) -> InlineKeyboardMarkup:
    rows = [[_btn("Использовать", f"pu:{profile_id}"), _btn("Скачать JSON", f"pj:{profile_id}")]]
    if site_url:
        rows.append(
            [InlineKeyboardButton(text="Открыть на сайте", url=f"{site_url}/profiles/{profile_id}")]
        )
    return _kb(rows)


def pager(prefix: str, page: int, pages: int) -> list[InlineKeyboardButton]:
    row = []
    if page > 0:
        row.append(_btn("‹", f"{prefix}:{page - 1}"))
    if page < pages - 1:
        row.append(_btn("›", f"{prefix}:{page + 1}"))
    return row


def profiles_pager(page: int, pages: int) -> InlineKeyboardMarkup:
    return _kb([pager("pp", page, pages), [_btn("В меню", "menu:main")]])


def job_actions(job_id: str, site_url: str, downloads: bool) -> InlineKeyboardMarkup:
    rows = []
    if downloads:
        rows.append([_btn("Скачать DOCX", f"hd:{job_id}"), _btn("Скачать PDF", f"hp:{job_id}")])
    if site_url:
        rows.append(
            [InlineKeyboardButton(text="Открыть на сайте", url=f"{site_url}/jobs/{job_id}")]
        )
    return _kb(rows)


def bases(names: list[str]) -> InlineKeyboardMarkup:
    return _kb([[_btn(n, f"gb:{i}")] for i, n in enumerate(names)])


def found(
    lines: list[tuple[int, str]], accepted: set[int], page: int, pages: int
) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{'✅' if i in accepted else '⬜'} {i + 1}. {label}"[:60], f"g:t:{i}")]
        for i, label in lines
    ]
    nav = pager("g:p", page, pages)
    if nav:
        rows.append(nav)
    rows.append([_btn("Создать профиль", "g:ok"), _btn("Отмена", "g:x")])
    return _kb(rows)


def created(profile_id: str, site_url: str) -> InlineKeyboardMarkup:
    rows = [[_btn("Использовать сейчас", f"pu:{profile_id}")]]
    if site_url:
        rows.append(
            [InlineKeyboardButton(text="Открыть на сайте", url=f"{site_url}/profiles/{profile_id}")]
        )
    rows.append([_btn("В меню", "menu:main")])
    return _kb(rows)
