from aiogram.methods import DeleteMessage, SendDocument


def test_profiles_list_use_goes_to_send_doc_with_profile(bot):
    bot.say("/start")
    bot.press_button("Мои профили")
    assert bot.session.texts()[-1] == "Мой профиль"
    assert bot.session.button_texts() == ["Использовать", "Скачать JSON", "Открыть на сайте"]
    urls = [b.url for row in bot.session.last_markup().inline_keyboard for b in row if b.url]
    assert urls == ["https://site.test/profiles/p1"]
    bot.press_button("Использовать")
    assert "Пришлите DOCX-файл или вставьте текст сообщением" in bot.session.texts()[-1]
    bot.send_document("a.docx", b"x")
    # профиль уже выбран: сразу режим, без списка профилей
    assert bot.session.button_texts() == [
        "Проверить — оставим комментарии",
        "Оформить — исправим сами",
    ]
    bot.press_button("Оформить — исправим сами")
    post = next(r for r in bot.fake_api.requests if r.method == "POST")
    assert b"p1" in post.content


def test_profile_json_download(bot):
    bot.say("/start")
    bot.press_button("Мои профили")
    bot.press_button("Скачать JSON")
    doc = bot.session.of(SendDocument)[0]
    assert doc.document.data == b'{"id": "p1"}'


def test_no_own_profiles(bot):
    bot.fake_api.profiles = bot.fake_api.profiles[:1]
    bot.say("/start")
    bot.press_button("Мои профили")
    assert "нет своих профилей" in bot.session.texts()[-1]
    assert bot.session.button_texts() == ["В меню"]


def test_history_five_jobs_downloads_only_for_done(bot):
    bot.say("/start")
    bot.press_button("История")
    job_msgs = [t for t in bot.session.texts() if "Мой профиль" in t]
    assert len(job_msgs) == 5
    assert "оформление" in job_msgs[0] and "готово" in job_msgs[0]
    assert "обрабатывается" in job_msgs[1]
    markups = [
        [b.text for row in c.reply_markup.inline_keyboard for b in row]
        for c in bot.session.calls
        if getattr(c, "text", None) in job_msgs
    ]
    assert markups[0][:2] == ["Скачать DOCX", "Скачать PDF"]
    assert markups[1] == ["Открыть на сайте"]
    assert sum("Скачать DOCX" in m for m in markups) == 4


def test_history_download(bot):
    bot.say("/start")
    bot.press_button("История")
    bot.press("hd:j1")
    assert bot.session.of(SendDocument)[0].document.data == b"DOCX-RESULT"


def test_empty_detail_falls_back_to_unavailable(bot):
    bot.fake_api.error = (500, "")
    bot.say("/start")
    bot.press_button("Оформить документ")
    bot.send_document("a.docx", b"x")
    bot.press_button("ГОСТ 7.32-2017")
    bot.press_button("Проверить — оставим комментарии")
    assert "Сервис временно недоступен, попробуйте позже" in bot.session.texts()[-1]


def test_create_failure_removes_stale_queue_message(bot):
    bot.fake_api.error = (429, "Лимит")
    bot.say("/start")
    bot.press_button("Оформить документ")
    bot.send_document("a.docx", b"x")
    bot.press_button("ГОСТ 7.32-2017")
    bot.press_button("Проверить — оставим комментарии")
    assert len(bot.session.of(DeleteMessage)) == 1


def test_help_mentions_limits_and_site(bot):
    bot.say("/start")
    bot.press_button("Помощь")
    assert "20 МБ" in bot.session.texts()[-1] and "https://site.test" in bot.session.texts()[-1]
