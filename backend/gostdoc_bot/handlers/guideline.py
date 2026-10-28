"""Профиль из методички: файл или текст -> ГОСТ-основа -> найденное -> профиль."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards, texts
from ..api import UNAVAILABLE, ApiClient, ApiError
from ..states import GuidelineFlow
from .common import (
    MAX_FILE,
    Availability,
    download_file,
    drop,
    main_menu,
    poll,
    too_big,
    who,
)
from .common import fail as _fail
from .common import reply as _reply

PAGE = 8
DEFAULT_BASE = "gost-7.32-2017"
QUOTE_CHARS = 150
UNSUPPORTED_SHOWN = 10
UNSUPPORTED_CHARS = 300
EXTENSIONS = (".docx", ".pdf")
LABELS = {"queued": texts.QUEUED, "running": texts.READING}


def _field_index(meta: dict) -> tuple[dict, dict, set]:
    fields = {(f["rule"], f["path"]): f for f in meta.get("fields", [])}
    seen, dup = set(), set()
    for f in fields.values():
        (dup if f["label"] in seen else seen).add(f["label"])
    return fields, meta.get("rule_labels", {}), dup


def _value(field: dict | None, value) -> str:
    if isinstance(value, bool):
        return "да" if value else "нет"
    if field:
        for opt in field.get("options") or []:
            if opt.get("value") == value:
                return str(opt.get("label", value))
        if field.get("unit"):
            return f"{value} {field['unit']}"
    return str(value)


def describe(item: dict, meta: dict) -> str:
    """«требование: значение» по подписям из /profile-fields."""
    fields, rule_labels, dup = _field_index(meta)
    rule, path = item.get("rule", ""), item.get("path", "")
    field = fields.get((rule, path))
    if field is None:
        label = f"{rule_labels.get(rule, rule)}, {path}"
    elif field["label"] in dup:
        label = f"{rule_labels.get(rule, rule)}, {field['label'].lower()}"
    else:
        label = field["label"]
    return f"{label}: {_value(field, item.get('value'))}"


def _detail(item: dict) -> str:
    quote = str(item.get("quote") or "")[:QUOTE_CHARS]
    out = f" — «{quote}»" if quote else ""
    if item.get("page"):
        out += f" (стр. {item['page']})"
    return out


def _render(data: dict, page: int) -> tuple[str, object]:
    labels, details = data["labels"], data["details"]
    accepted = set(data["acc"])
    pages = (len(labels) + PAGE - 1) // PAGE
    page = min(max(page, 0), pages - 1)
    idxs = range(page * PAGE, min((page + 1) * PAGE, len(labels)))
    body = "\n".join(f"{i + 1}. {labels[i]}{details[i]}" for i in idxs)
    head = texts.FOUND_HEAD.format(n=len(labels), page=page + 1, pages=pages)
    markup = keyboards.found([(i, labels[i]) for i in idxs], accepted, page, pages)
    return f"{head}\n\n{body}", markup


def _unsupported_text(items: list[dict]) -> str:
    lines = [texts.UNSUPPORTED_HEAD]
    for item in items[:UNSUPPORTED_SHOWN]:
        text = str(item.get("text", ""))[:UNSUPPORTED_CHARS]
        lines.append(f"• {text}{_detail(item)}")
    return "\n".join(lines)


async def _ask_base(message: Message, user, state: FSMContext, api: ApiClient) -> None:
    uid, name = who(user)
    try:
        profiles = await api.profiles(uid, name)
    except ApiError as exc:
        return await _fail(message, exc, state)
    bases = [p for p in profiles if p.get("readonly")]
    bases.sort(key=lambda p: p["id"] != DEFAULT_BASE)  # стабильно: ГОСТ 7.32-2017 первым
    if not bases:
        await state.clear()
        return await message.answer(texts.NO_PROFILES, reply_markup=keyboards.to_menu())
    await state.update_data(base_ids=[p["id"] for p in bases])
    await state.set_state(GuidelineFlow.choosing_base)
    await message.answer(
        texts.CHOOSE_BASE, reply_markup=keyboards.bases([p["name"] for p in bases])
    )


async def _finish_text(message: Message, user, state: FSMContext, api: ApiClient) -> None:
    if not (await state.get_data()).get("parts"):
        return await message.answer(texts.SEND_GUIDELINE)
    await _ask_base(message, user, state, api)


async def _show_result(
    message: Message, api: ApiClient, uid: int, name: str | None, state: FSMContext, ext: dict
) -> None:
    result = ext.get("result") or {}
    found = result.get("found") or []
    unsupported = result.get("unsupported") or []
    if not found:
        await state.clear()
        out = texts.NOTHING_FOUND
        if unsupported:
            out += "\n\n" + _unsupported_text(unsupported)
        return await message.answer(out, reply_markup=keyboards.to_menu())
    try:
        meta = await api.profile_fields(uid, name)
    except ApiError:
        meta = {}  # без подписей показываем коды правил
    data = {
        "eid": ext["id"],
        "labels": [describe(it, meta) for it in found],
        "details": [_detail(it) for it in found],
        "acc": list(range(len(found))),
        "page": 0,
    }
    await state.set_data({**(await state.get_data()), **data})
    await state.set_state(GuidelineFlow.reviewing)
    if unsupported:
        await message.answer(_unsupported_text(unsupported))
    text, markup = _render(data, 0)
    await message.answer(text, reply_markup=markup)


def build_router():
    router = Router(name="guideline")

    @router.callback_query(F.data == "menu:extract")
    async def begin(cb: CallbackQuery, state: FSMContext) -> None:
        await cb.answer()
        await state.clear()
        await state.set_state(GuidelineFlow.waiting_input)
        await state.update_data(parts=[], file_id=None, file_name=None)
        await cb.message.answer(texts.SEND_GUIDELINE)

    @router.message(StateFilter(GuidelineFlow.waiting_input), F.document)
    async def got_document(message: Message, state: FSMContext, api: ApiClient) -> None:
        doc = message.document
        if (doc.file_size or 0) > MAX_FILE:
            return await message.answer(texts.FILE_TOO_BIG, reply_markup=keyboards.to_menu())
        if not (doc.file_name or "").lower().endswith(EXTENSIONS):
            return await message.answer(texts.SEND_GUIDELINE)
        await state.update_data(file_id=doc.file_id, file_name=doc.file_name, parts=[])
        await _ask_base(message, message.from_user, state, api)

    @router.message(StateFilter(GuidelineFlow.waiting_input), F.text.casefold() == "готово")
    async def text_done(message: Message, state: FSMContext, api: ApiClient) -> None:
        await _finish_text(message, message.from_user, state, api)

    @router.callback_query(StateFilter(GuidelineFlow.waiting_input), F.data == "fdone")
    async def text_done_button(cb: CallbackQuery, state: FSMContext, api: ApiClient) -> None:
        await cb.answer()
        await _finish_text(cb.message, cb.from_user, state, api)

    @router.message(StateFilter(GuidelineFlow.waiting_input), F.text, ~F.text.startswith("/"))
    async def got_text(message: Message, state: FSMContext) -> None:
        parts = [*(await state.get_data()).get("parts", []), message.text]
        await state.update_data(parts=parts, file_id=None, file_name=None)
        total = sum(len(p) for p in parts)
        await message.answer(
            texts.TEXT_ACCEPTED.format(n=total), reply_markup=keyboards.text_done()
        )

    @router.message(StateFilter(GuidelineFlow.waiting_input))
    async def wrong_input(message: Message) -> None:
        await message.answer(texts.SEND_GUIDELINE)

    @router.callback_query(StateFilter(GuidelineFlow.choosing_base), F.data.regexp(r"^gb:\d+$"))
    async def chose_base(
        cb: CallbackQuery,
        state: FSMContext,
        bot: Bot,
        api: ApiClient,
        avail: Availability,
        poll_interval: float = 2.0,
    ) -> None:
        await cb.answer()
        data = await state.get_data()
        ids = data.get("base_ids", [])
        idx = int(cb.data.split(":")[1])
        if idx >= len(ids):
            await state.clear()
            return await cb.message.answer(
                texts.RESTART, reply_markup=await main_menu(avail, cb.from_user)
            )
        uid, name = who(cb.from_user)
        status = None
        try:
            status = await cb.message.answer(texts.QUEUED)
            file = text = None
            if data.get("file_id"):
                file = await download_file(bot, data["file_id"], data.get("file_name") or "in.docx")
            else:
                text = "\n".join(data.get("parts", []))
            ext = await api.create_extraction(uid, name, file, text, ids[idx])
        except ApiError as exc:  # состояние сохраняем: можно выбрать основу ещё раз
            await drop(status)
            return await _reply(cb.message, exc.detail)
        except TelegramAPIError as exc:
            await drop(status)
            return await _reply(cb.message, texts.FILE_TOO_BIG if too_big(exc) else UNAVAILABLE)
        await state.update_data(file_id=None, parts=[])
        try:
            final = await poll(
                status, lambda: api.extraction(uid, name, ext["id"]), LABELS, poll_interval
            )
        except ApiError as exc:
            return await _reply(cb.message, exc.detail)
        if final is None:
            return await _reply(cb.message, texts.JOB_TIMEOUT)
        if final["status"] != "done":
            return await _reply(cb.message, final.get("error") or texts.JOB_FAILED)
        await _show_result(cb.message, api, uid, name, state, final)

    async def _edit(cb: CallbackQuery, data: dict, page: int) -> None:
        text, markup = _render(data, page)
        try:
            await cb.message.edit_text(text, reply_markup=markup)
        except TelegramAPIError:
            pass  # «message is not modified» и подобное

    @router.callback_query(StateFilter(GuidelineFlow.reviewing), F.data.regexp(r"^g:t:\d+$"))
    async def toggle(cb: CallbackQuery, state: FSMContext, avail: Availability) -> None:
        data = await state.get_data()
        idx = int(cb.data.split(":")[2])
        if idx >= len(data.get("labels", [])):
            await cb.answer()
            await state.clear()
            return await cb.message.answer(
                texts.RESTART, reply_markup=await main_menu(avail, cb.from_user)
            )
        await cb.answer()
        acc = set(data["acc"])
        acc ^= {idx}
        data["acc"] = sorted(acc)
        await state.update_data(acc=data["acc"], page=idx // PAGE)
        await _edit(cb, data, idx // PAGE)

    @router.callback_query(StateFilter(GuidelineFlow.reviewing), F.data.regexp(r"^g:p:\d+$"))
    async def turn_page(cb: CallbackQuery, state: FSMContext) -> None:
        await cb.answer()
        data = await state.get_data()
        page = int(cb.data.split(":")[2])
        await state.update_data(page=page)
        await _edit(cb, data, page)

    @router.callback_query(StateFilter(GuidelineFlow.reviewing), F.data == "g:ok")
    async def ask_name(cb: CallbackQuery, state: FSMContext) -> None:
        if not (await state.get_data()).get("acc"):
            return await cb.answer(texts.PICK_ONE, show_alert=True)
        await cb.answer()
        await state.set_state(GuidelineFlow.naming)
        await cb.message.answer(texts.ASK_NAME)

    @router.callback_query(
        StateFilter(GuidelineFlow.reviewing, GuidelineFlow.naming), F.data == "g:x"
    )
    async def cancel(cb: CallbackQuery, state: FSMContext, avail: Availability) -> None:
        await cb.answer()
        await state.clear()
        await cb.message.answer(texts.MENU, reply_markup=await main_menu(avail, cb.from_user))

    @router.message(StateFilter(GuidelineFlow.naming), F.text, ~F.text.startswith("/"))
    async def named(
        message: Message, state: FSMContext, api: ApiClient, site_url: str = ""
    ) -> None:
        data = await state.get_data()
        title = message.text.strip()
        if title == "-":
            stem = (data.get("file_name") or "").rsplit(".", 1)[0].strip()
            title = stem or texts.DEFAULT_PROFILE_NAME
        title = title[:255]
        uid, name = who(message.from_user)
        try:
            created = await api.create_profile_from_extraction(
                uid, name, data["eid"], sorted(data["acc"]), title
            )
        except ApiError as exc:
            return await _reply(message, exc.detail)
        await state.clear()
        await message.answer(
            texts.PROFILE_CREATED.format(name=title),
            reply_markup=keyboards.created(created["profile_id"], site_url),
        )

    return router
