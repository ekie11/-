import io
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis
import pytest
from docx import Document
from rq import Queue
from rq.timeouts import JobTimeoutException

from gostdoc_api import extraction, worker
from gostdoc_api.cleanup import cleanup_expired
from gostdoc_api.llm import LlmError
from gostdoc_api.models import Extraction
from gostdoc_api.queue import get_queue, on_extraction_failure

from .test_profiles import GOST, reg

TEXT = "Требования. Левое поле — 30 мм, правое — 10 мм. Кегль 14 пт."
LLM_DOWN = "Сервис распознавания временно недоступен, попробуйте позже"
GENERIC = "Не удалось обработать методичку"


def answer(*_a, **_k):
    return {
        "found": [
            {"rule": "page.margins", "path": "left_mm", "value": 30, "quote": "Левое поле — 30 мм"},
            {"rule": "page.margins", "path": "right_mm", "value": 10, "quote": "правое — 10 мм"},
            {"rule": "body.font_size", "path": "target_pt", "value": 14, "quote": "Кегль 14 пт"},
        ],
        "unsupported": [],
    }


@pytest.fixture(autouse=True)
def llm_key(monkeypatch, settings):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setattr(extraction, "chat_json", answer)
    from gostdoc_api.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def app(settings, monkeypatch):
    from gostdoc_api.app import create_app
    from gostdoc_api.config import get_settings
    from gostdoc_api.models import Base

    get_settings.cache_clear()
    app = create_app(get_settings())
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def queue(app):
    q = Queue(is_async=False, connection=fakeredis.FakeStrictRedis())
    app.dependency_overrides[get_queue] = lambda: q
    return q


def post(client, **kw):
    data = {"base_profile_id": GOST, **kw.pop("data", {})}
    return client.post("/extractions", data=data, **kw)


def make(client, data=None):
    r = post(client, data=data or {"text": TEXT})
    assert r.status_code == 202, r.text
    return r.json()["id"]


def test_guest_401_and_no_key_503(client, queue, monkeypatch):
    assert post(client, data={"text": TEXT}).status_code == 401
    reg(client)
    st = client.app.state
    st.settings = replace(st.settings, llm_api_key="")
    r = post(client, data={"text": TEXT})
    assert r.status_code == 503 and r.json()["detail"] == "Функция не настроена"


def test_end_to_end_and_ownership(client, queue):
    reg(client)
    eid = make(client)
    got = client.get(f"/extractions/{eid}").json()
    assert got["status"] == "done" and len(got["result"]["found"]) == 3
    assert got["base_profile_id"] == GOST
    client.post("/auth/logout")
    reg(client, "b@example.com")
    assert client.get(f"/extractions/{eid}").status_code == 404
    assert (
        client.post(f"/extractions/{eid}/profile", json={"accepted": [], "name": "x"}).status_code
        == 404
    )


def test_validation(client, queue):
    reg(client)
    assert post(client).json()["detail"] == "Загрузите файл или вставьте текст"
    r = post(client, data={"text": TEXT, "base_profile_id": "nope"})
    assert r.status_code == 400 and r.json()["detail"] == "Базовый профиль не найден"
    r = post(client, data={"text": "x" * 150_001})
    assert r.status_code == 413
    r = post(client, data={"text": "  "})
    assert r.status_code == 400
    assert queue.count == 0
    # скан-PDF: в БД ничего
    pdf = b"%PDF-1.4\n"
    r = post(client, files={"file": ("a.pdf", pdf, "application/pdf")})
    assert r.status_code == 400


def test_file_upload_docx(client, queue):
    reg(client)
    d = Document()
    d.add_paragraph(TEXT)
    buf = io.BytesIO()
    d.save(buf)
    r = post(client, files={"file": ("m.docx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 202
    assert client.get(f"/extractions/{r.json()['id']}").json()["source_name"] == "m.docx"


def test_user_limit_and_quota(client, queue):
    reg(client)
    for _ in range(5):
        make(client)
    assert client.get("/extractions/quota").json() == {"used": 5, "limit": 5}
    r = post(client, data={"text": TEXT})
    assert r.status_code == 429 and r.json()["detail"] == "Лимит извлечений на сегодня исчерпан"


def test_global_limit(client, queue):
    st = client.app.state
    st.settings = replace(st.settings, extract_global_daily=2)
    reg(client, "a@example.com")
    make(client)
    client.post("/auth/logout")
    reg(client, "b@example.com")
    make(client)
    r = post(client, data={"text": TEXT})
    assert r.status_code == 429 and r.json()["detail"] == "Сервис перегружен, попробуйте завтра"


def test_llm_error_not_counted(client, queue, monkeypatch):
    def boom(*a, **k):
        raise LlmError("x")

    monkeypatch.setattr(extraction, "chat_json", boom)
    reg(client)
    eid = make(client)
    got = client.get(f"/extractions/{eid}").json()
    assert got["status"] == "failed" and got["error"] == LLM_DOWN
    assert client.get("/extractions/quota").json()["used"] == 0


def test_worker_exception_failed_counted(client, queue, monkeypatch):
    def boom(*a, **k):
        raise ValueError("секретный текст методички")

    monkeypatch.setattr(extraction, "validate", boom)
    reg(client)
    eid = make(client)
    got = client.get(f"/extractions/{eid}").json()
    assert got["status"] == "failed" and got["error"] == GENERIC
    assert client.get("/extractions/quota").json()["used"] == 1


def test_failure_callback_marks_failed(client, queue, db_session):
    reg(client)
    row = Extraction(
        id="e1", user_id=1, status="running", base_profile_id=GOST, counts_toward_limit=True
    )
    db_session.add(row)
    db_session.commit()
    on_extraction_failure(SimpleNamespace(id="e1"), None, JobTimeoutException, None, None)
    db_session.expire_all()
    got = db_session.get(Extraction, "e1")
    assert got.status == "failed" and got.error == worker.TIMEOUT_MESSAGE


def test_build_profile(client, queue):
    reg(client)
    eid = make(client)
    r = client.post(f"/extractions/{eid}/profile", json={"accepted": [0, 2], "name": "  Мой  "})
    assert r.status_code == 201
    p = client.get(f"/profiles/{r.json()['profile_id']}").json()
    base = client.get(f"/profiles/{GOST}").json()
    assert p["name"] == "Мой" and p["base"] == GOST and p["readonly"] is False
    assert p["rules"]["page.margins"]["value"]["left_mm"] == 30
    assert (
        p["rules"]["page.margins"]["value"]["right_mm"]
        == base["rules"]["page.margins"]["value"]["right_mm"]
    )
    assert p["rules"]["body.font_size"]["value"]["target_pt"] == 14
    assert p["rules"]["body.font_size"]["enabled"] is True


def test_profile_empty_accepted_and_twice(client, queue):
    reg(client)
    eid = make(client)
    ids = set()
    for _ in range(2):
        r = client.post(f"/extractions/{eid}/profile", json={"accepted": [], "name": "Копия"})
        assert r.status_code == 201
        ids.add(r.json()["profile_id"])
    assert len(ids) == 2
    p = client.get(f"/profiles/{ids.pop()}").json()
    base = client.get(f"/profiles/{GOST}").json()
    assert p["rules"] == base["rules"]


def test_profile_errors(client, queue):
    reg(client)
    eid = make(client)
    url = f"/extractions/{eid}/profile"
    assert client.post(url, json={"accepted": [9], "name": "x"}).status_code == 400
    assert client.post(url, json={"accepted": [-1], "name": "x"}).status_code == 400
    assert client.post(url, json={"accepted": [], "name": "   "}).status_code in (400, 422)
    assert client.post(url, json={"accepted": [], "name": "x" * 256}).status_code in (400, 422)


def test_profile_409_when_not_done(client, queue, db_session):
    reg(client)
    db_session.add(Extraction(id="q1", user_id=1, status="queued", base_profile_id=GOST))
    db_session.commit()
    r = client.post("/extractions/q1/profile", json={"accepted": [], "name": "x"})
    assert r.status_code == 409


def test_cleanup_removes_old(client, queue, db_session, settings):
    reg(client)
    old = datetime.now(UTC) - timedelta(days=settings.file_ttl_days + 1)
    db_session.add(
        Extraction(id="old", user_id=1, status="done", base_profile_id=GOST, created_at=old)
    )
    db_session.add(Extraction(id="new", user_id=1, status="done", base_profile_id=GOST))
    db_session.commit()
    cleanup_expired(db_session, settings, datetime.now(UTC))
    ids = {e.id for e in db_session.query(Extraction)}
    assert ids == {"new"}


def test_enqueue_does_not_keep_text_in_redis(client, queue, monkeypatch):
    calls = []
    orig = queue.enqueue

    def spy(*a, **kw):
        calls.append(kw)
        return orig(*a, **kw)

    monkeypatch.setattr(queue, "enqueue", spy)
    reg(client)
    make(client)
    kw = calls[0]
    assert kw["result_ttl"] == 0 and kw["failure_ttl"] == 60
    assert kw["ttl"] == kw["job_timeout"]
