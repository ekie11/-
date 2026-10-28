from aiogram.methods import DeleteMessage

from tests.bot.conftest import multipart_fields

MENU_NO_EXTRACT = ["Оформить документ", "Мои профили", "История", "Помощь"]


def to_base(bot):
    bot.say("/start")
    bot.press_button("Создать профиль из методички")
    bot.send_document("методичка.docx", b"GUIDE")


def to_review(bot):
    to_base(bot)
    bot.press_button("ГОСТ 7.32-2017")


def test_ten_found_two_pages_toggle_and_create(bot):
    to_review(bot)
    texts = bot.session.texts()
    assert "Читаем методичку…" in texts
    assert any("Не поддерживается" in t and "Шрифт Arial" in t for t in texts)
    page = texts[-1]
    assert "1. Верхнее поле: 20 мм — «поле 0» (стр. 2)" in page
    assert "8. " in page and "9. " not in page
    buttons = bot.session.button_texts()
    assert buttons[0].startswith("✅ 1.") and "›" in buttons
    cb = bot.session.callback_for(buttons[0])
    assert cb == "g:t:0" and len(cb.encode()) <= 64
    bot.press_button(buttons[0])  # снимаем первый
    assert bot.session.button_texts()[0].startswith("⬜ 1.")
    bot.press("g:p:1")
    assert "9. " in bot.session.texts()[-1] and "10. " in bot.session.texts()[-1]
    assert "‹" in bot.session.button_texts()
    bot.press_button("Создать профиль")
    assert "Как назвать профиль? («-» — по имени файла)" in bot.session.texts()[-1]
    bot.say("-")
    assert bot.fake_api.profile_posts == [{"accepted": list(range(1, 10)), "name": "методичка"}]
    assert "Профиль «методичка» создан" in bot.session.texts()[-1]
    assert bot.session.button_texts() == ["Использовать сейчас", "Открыть на сайте", "В меню"]
    bot.press_button("Использовать сейчас")


def test_use_now_preselects_created_profile(bot):
    bot.fake_api.profiles.append({"id": "new1", "name": "Новый", "base": None, "readonly": False})
    to_review(bot)
    bot.press_button("Создать профиль")
    bot.say("Новый")
    assert bot.fake_api.profile_posts[0]["name"] == "Новый"
    bot.press_button("Использовать сейчас")
    assert "Профиль: Новый" in bot.session.texts()[-1]


def test_base_buttons_gosts_only_default_first(bot):
    bot.fake_api.profiles = [
        {"id": "other", "name": "ГОСТ Р 7.0.97", "base": None, "readonly": True},
        {"id": "gost-7.32-2017", "name": "ГОСТ 7.32-2017", "base": None, "readonly": True},
        {"id": "p1", "name": "Мой профиль", "base": "x", "readonly": False},
    ]
    to_base(bot)
    assert bot.session.button_texts() == ["ГОСТ 7.32-2017", "ГОСТ Р 7.0.97"]
    bot.press_button("ГОСТ Р 7.0.97")
    post = next(r for r in bot.fake_api.requests if r.url.path == "/extractions")
    assert multipart_fields(post)["base_profile_id"] == b"other"


def test_nothing_selected_cannot_create(bot):
    bot.fake_api.found = bot.fake_api.found[:1]
    to_review(bot)
    bot.press("g:t:0")
    n = len(bot.session.texts())
    bot.press("g:ok")
    assert len(bot.session.texts()) == n and not bot.fake_api.profile_posts


def test_text_input_and_pdf_accepted_other_rejected(bot):
    bot.say("/start")
    bot.press_button("Создать профиль из методички")
    bot.send_document("a.zip", b"x")
    assert "Пришлите методичку" in bot.session.texts()[-1]
    bot.say("Поля 20 мм")
    bot.say("Готово")
    bot.press_button("ГОСТ 7.32-2017")
    post = next(r for r in bot.fake_api.requests if r.url.path == "/extractions")
    assert multipart_fields(post)["text"] == "Поля 20 мм".encode()
    bot.press_button("Создать профиль")
    bot.say("-")
    assert bot.fake_api.profile_posts[0]["name"] == "Профиль из методички"


def test_pdf_and_big_file(bot):
    bot.say("/start")
    bot.press_button("Создать профиль из методички")
    bot.send_document("big.pdf", b"x", size=21 * 1024 * 1024)
    assert "Файл больше 20 МБ" in bot.session.texts()[-1]
    bot.send_document("ok.pdf", b"%PDF")
    assert bot.session.button_texts() == ["ГОСТ 7.32-2017"]


def test_limit_error_shows_detail_and_drops_status(bot):
    bot.fake_api.error = (429, "Лимит извлечений на сегодня исчерпан")
    to_review(bot)
    assert "Лимит извлечений" in bot.session.texts()[-1]
    assert len(bot.session.of(DeleteMessage)) == 1


def test_failed_extraction_shows_error(bot):
    bot.fake_api.extraction_statuses = ["failed"]
    bot.fake_api.extraction_error = "Не вышло"
    to_review(bot)
    assert "Не вышло" in bot.session.texts()[-1]


def test_feature_off_hides_menu_button(bot):
    bot.fake_api.extraction_enabled = False
    bot.say("/start")
    assert bot.session.button_texts() == MENU_NO_EXTRACT


def test_availability_cached_and_network_error_keeps_button(bot):
    bot.say("/start")
    bot.say("/start")
    quota_calls = [r for r in bot.fake_api.requests if r.url.path == "/profile-fields"]
    assert len(quota_calls) == 1
    assert "Создать профиль из методички" in bot.session.button_texts()


def test_stale_guideline_buttons(bot):
    bot.press("g:t:0")
    assert "Начните заново" in bot.session.texts()[-1]


def test_feature_on_shows_menu_button(bot):
    bot.say("/start")
    assert "Создать профиль из методички" in bot.session.button_texts()


def test_availability_network_error_keeps_button_uncached(bot):
    bot.fake_api.network_down = True
    bot.say("/start")
    assert "Создать профиль из методички" in bot.session.button_texts()
    bot.fake_api.network_down = False
    bot.fake_api.extraction_enabled = False
    bot.say("/start")
    assert bot.session.button_texts() == MENU_NO_EXTRACT


def test_long_unsupported_split_and_all_messages_fit(bot):
    bot.fake_api.unsupported = [
        {"text": "я" * 400, "quote": "ц" * 400, "page": 1} for _ in range(10)
    ]
    to_review(bot)
    texts = bot.session.texts()
    assert all(len(t) <= 4096 for t in texts)
    assert sum("•" in t for t in texts) >= 2
    assert "Найдено требований" in texts[-1]


def test_telegram_failure_on_result_gives_unavailable(bot):
    from aiogram.exceptions import TelegramNetworkError
    from aiogram.methods import SendMessage

    to_base(bot)
    bot.fake_api.extraction_statuses = ["done"]
    real = bot.session.make_request

    async def flaky(b, method, timeout=None):
        if isinstance(method, SendMessage) and "Найдено требований" in method.text:
            raise TelegramNetworkError(method, "net")
        return await real(b, method, timeout)

    bot.session.make_request = flaky
    bot.press_button("ГОСТ 7.32-2017")
    assert "Сервис временно недоступен" in bot.session.texts()[-1]


def test_status_removed_after_success_and_failure(bot):
    to_review(bot)
    assert len(bot.session.of(DeleteMessage)) == 1


def test_status_removed_after_failed_extraction(bot):
    bot.fake_api.extraction_statuses = ["failed"]
    to_review(bot)
    assert len(bot.session.of(DeleteMessage)) == 1


def test_double_tap_creates_one_extraction(bot):
    to_base(bot)
    cb = bot.session.callback_for("ГОСТ 7.32-2017")
    bot.press(cb)
    bot.press(cb)
    posts = [r for r in bot.fake_api.requests if r.url.path == "/extractions" and r.method == "POST"]
    assert len(posts) == 1


def test_concurrent_double_tap_creates_one_extraction(bot):
    import asyncio
    from datetime import UTC, datetime

    from aiogram.types import CallbackQuery, Message, Update

    from tests.bot.conftest import CHAT, USER

    to_base(bot)
    data = bot.session.callback_for("ГОСТ 7.32-2017")

    def update(i):
        msg = Message(message_id=1, date=datetime.now(UTC), chat=CHAT, text="старое")
        cq = CallbackQuery(
            id=str(i), from_user=USER, chat_instance="c", message=msg, data=data
        )
        return Update(update_id=900 + i, callback_query=cq)

    async def both():
        await asyncio.gather(
            bot.dp.feed_update(bot.bot, update(1)), bot.dp.feed_update(bot.bot, update(2))
        )

    asyncio.run(both())
    posts = [r for r in bot.fake_api.requests if r.url.path == "/extractions" and r.method == "POST"]
    assert len(posts) == 1


def test_unexpected_error_resets_state_and_answers(bot):
    to_base(bot)
    original = bot.fake_api.handler

    def boom(request):
        if request.url.path == "/extractions/e1":
            raise RuntimeError("boom")
        return original(request)

    bot.dp.workflow_data["api"]._http._transport = __import__("httpx").MockTransport(boom)
    bot.press_button("ГОСТ 7.32-2017")
    assert "Сервис временно недоступен" in bot.session.texts()[-1]
    assert len(bot.session.of(DeleteMessage)) == 1
    bot.press("gb:0")  # состояние сброшено
    assert "Начните заново" in bot.session.texts()[-1]
