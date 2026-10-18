def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings_defaults(settings):
    assert settings.cookie_secure is False
    assert settings.soffice_path == "soffice"
    assert settings.job_timeout_s == 120
    assert settings.file_ttl_days == 30


def test_body_over_cap_413_by_content_length(client):
    r = client.post("/jobs", content=b"x", headers={"Content-Length": str(21 * 1024 * 1024 + 1)})
    assert r.status_code == 413
    assert r.json() == {"detail": "Файл слишком большой — максимум 20 МБ"}


def test_chunked_body_over_cap_413(client):
    from .test_profiles import reg

    reg(client)

    def gen():
        yield (
            b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.docx"\r\n'
            b"Content-Type: application/octet-stream\r\n\r\n"
        )
        chunk = b"x" * (1024 * 1024)
        for _ in range(22):
            yield chunk
        yield b"\r\n--x--\r\n"

    r = client.post(
        "/jobs", content=gen(), headers={"Content-Type": "multipart/form-data; boundary=x"}
    )
    assert r.status_code == 413
    assert r.json()["detail"] == "Файл слишком большой — максимум 20 МБ"


def test_oversized_body_is_drained_before_413():
    import asyncio
    import json

    from gostdoc_api.app import BodyLimitMiddleware

    async def inner(scope, receive, send):  # не должен вызываться из-за Content-Length
        raise AssertionError

    chunks = [b"x" * (1024 * 1024)] * 22
    consumed = 0
    events = []

    async def receive():
        nonlocal consumed
        if consumed < len(chunks):
            consumed += 1
            return {
                "type": "http.request",
                "body": chunks[consumed - 1],
                "more_body": consumed < len(chunks),
            }
        return {"type": "http.disconnect"}

    async def send(message):
        events.append((consumed, message))

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/jobs",
        "headers": [(b"content-length", str(22 * 1024 * 1024).encode())],
    }
    asyncio.run(BodyLimitMiddleware(inner)(scope, receive, send))
    start = next(m for _, m in events if m["type"] == "http.response.start")
    body = next(m for _, m in events if m["type"] == "http.response.body")
    assert start["status"] == 413
    assert json.loads(body["body"]) == {"detail": "Файл слишком большой — максимум 20 МБ"}
    assert events[0][0] == len(chunks)  # тело дочитано до отправки ответа


def test_missing_database_url_warns(settings, monkeypatch, caplog):
    import logging

    from gostdoc_api.app import create_app

    monkeypatch.delenv("DATABASE_URL")
    with caplog.at_level(logging.WARNING, logger="gostdoc_api.app"):
        create_app(settings)
    assert any("DATABASE_URL" in r.getMessage() for r in caplog.records)


def test_database_url_set_no_warning(settings, caplog):
    import logging

    from gostdoc_api.app import create_app

    with caplog.at_level(logging.WARNING, logger="gostdoc_api.app"):
        create_app(settings)
    assert not any("DATABASE_URL" in r.getMessage() for r in caplog.records)


def test_extraction_queue_is_separate():
    from gostdoc_api.queue import EXTRACTION_QUEUE_NAME, QUEUE_NAME

    assert EXTRACTION_QUEUE_NAME == "extractions" != QUEUE_NAME
