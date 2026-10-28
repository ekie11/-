from urllib.parse import quote

from aiogram.methods import SendDocument

from tests.bot.conftest import multipart_fields

MENU = ["Оформить документ", "Мои профили", "Создать профиль из методички", "История", "Помощь"]


def start_format(bot):
    bot.say("/start")
    bot.press_button("Оформить документ")


def test_start_shows_menu_of_five_buttons(bot):
    bot.say("/start")
    assert bot.session.button_texts() == MENU


def test_docx_flow_to_result(bot):
    start_format(bot)
    assert "Пришлите DOCX-файл или вставьте текст сообщением" in bot.session.texts()[-1]
    bot.send_document("курсовая.docx", b"DOCXDATA")
    assert bot.session.button_texts() == ["ГОСТ 7.32-2017", "Мой профиль"]
    bot.press_button("Мой профиль")
    assert bot.session.button_texts() == [
        "Проверить — оставим комментарии",
        "Оформить — исправим сами",
    ]
    bot.press_button("Оформить — исправим сами")

    texts = bot.session.texts()
    assert any("Обрабатываем" in t for t in texts)
    result = next(t for t in texts if "12 замечаний" in t)
    assert "Замечание 9" in result and "Замечание 10" not in result
    docs = bot.session.of(SendDocument)
    assert len(docs) == 2
    assert docs[0].document.data == b"DOCX-RESULT"
    assert docs[1].document.data == b"PDF-RESULT"
    markup = bot.session.last_markup()
    urls = [b.url for row in markup.inline_keyboard for b in row if b.url]
    assert urls == ["https://site.test/jobs/j1"]

    post = next(r for r in bot.fake_api.requests if r.method == "POST")
    fields = multipart_fields(post)
    assert fields["profile_id"] == b"p1" and fields["mode"] == b"format"
    assert b"DOCXDATA" in fields["file"]
    assert post.headers["X-Bot-Secret"] == "s3cret"
    assert post.headers["X-Telegram-User"] == "42"
    assert post.headers["X-Telegram-Name"] == quote("Иван Петров")


def test_text_in_two_messages_sent_as_one_string(bot):
    start_format(bot)
    bot.say("первая часть")
    bot.say("вторая часть")
    bot.say("Готово")
    bot.press_button("ГОСТ 7.32-2017")
    bot.press_button("Проверить — оставим комментарии")
    post = next(r for r in bot.fake_api.requests if r.method == "POST")
    fields = multipart_fields(post)
    assert fields["text"].decode() == "первая часть\nвторая часть"
    assert "file" not in fields


def test_limit_error_shows_detail_and_menu_button(bot):
    bot.fake_api.error = (429, "Лимит на сегодня исчерпан")
    start_format(bot)
    bot.send_document("a.docx", b"x")
    bot.press_button("ГОСТ 7.32-2017")
    bot.press_button("Проверить — оставим комментарии")
    assert "Лимит на сегодня исчерпан" in bot.session.texts()[-1]
    assert bot.session.button_texts() == ["В меню"]


def test_file_over_20_mb(bot):
    start_format(bot)
    bot.send_document("big.docx", b"x", size=21 * 1024 * 1024)
    assert "Файл больше 20 МБ" in bot.session.texts()[-1]


def test_photo_and_pdf_rejected_state_kept(bot):
    start_format(bot)
    bot.send_photo()
    assert "Пришлите DOCX-файл или вставьте текст сообщением" in bot.session.texts()[-1]
    bot.send_document("a.pdf", b"%PDF")
    assert "Пришлите DOCX-файл или вставьте текст сообщением" in bot.session.texts()[-1]
    bot.send_document("ok.docx", b"x")
    assert bot.session.button_texts() == ["ГОСТ 7.32-2017", "Мой профиль"]


def test_stale_callback_without_state(bot):
    bot.press("fp:0")
    assert "Начните заново" in bot.session.texts()[-1]
    assert bot.session.button_texts() == MENU
