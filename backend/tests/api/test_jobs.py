import io
import json
from types import SimpleNamespace

import fakeredis
import pytest
from docx import Document
from rq import Queue
from rq.timeouts import JobTimeoutException

from gostdoc_api import worker
from gostdoc_api.models import Job
from gostdoc_api.pdf import PdfError
from gostdoc_api.queue import get_queue, on_job_failure
from gostdoc_engine.textguard import TextChangedError
from tests.builders import build_docx, save

from .test_profiles import GOST, make_own, reg

GENERIC = "Не удалось обработать документ, попробуйте ещё раз"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def bad_docx() -> bytes:
    return save(build_docx([("h1", "Введение"), ("p", "Текст работы.")], font="Arial", size_pt=10))


@pytest.fixture(autouse=True)
def fake_pdf(monkeypatch):
    def fake(docx_path, out_dir, *, soffice, timeout_s):
        out = out_dir / (docx_path.stem + ".pdf")
        out.write_bytes(b"%PDF-1.4")
        return out

    monkeypatch.setattr(worker, "render_pdf", fake)


@pytest.fixture
def redis_conn():
    return fakeredis.FakeStrictRedis()


@pytest.fixture
def queue(app, redis_conn):
    q = Queue(is_async=False, connection=redis_conn)
    app.dependency_overrides[get_queue] = lambda: q
    return q


@pytest.fixture
def deferred_queue(app, redis_conn):
    q = Queue(is_async=True, connection=redis_conn)
    app.dependency_overrides[get_queue] = lambda: q
    return q


def post(client, **kw):
    data = {"profile_id": GOST, "mode": "check", **kw.pop("data", {})}
    return client.post("/jobs", data=data, **kw)


def upload(client, content, **data):
    return post(client, data=data, files={"file": ("a.docx", content, DOCX_TYPE)})


def test_check_docx_end_to_end(client, queue):
    reg(client)
    r = upload(client, bad_docx())
    assert r.status_code == 202
    jid = r.json()["id"]
    got = client.get(f"/jobs/{jid}").json()
    assert got["status"] == "done" and got["has_pdf"] is True
    assert got["report"]["summary"]["errors"] > 0
    d = client.get(f"/jobs/{jid}/docx")
    assert d.status_code == 200 and d.headers["content-type"] == DOCX_TYPE
    doc = Document(io.BytesIO(d.content))
    assert len(list(doc.comments)) > 0
    assert client.get(f"/jobs/{jid}/pdf").content == b"%PDF-1.4"
    lst = client.get("/jobs").json()
    assert lst[0]["profile_name"] == "ГОСТ 7.32-2017" and lst[0]["id"] == jid


def test_format_text_end_to_end(client, queue):
    reg(client)
    r = post(client, data={"mode": "format", "text": "ВВЕДЕНИЕ\nОбычный текст работы."})
    assert r.status_code == 202
    got = client.get(f"/jobs/{r.json()['id']}").json()
    assert got["status"] == "done", got
    assert got["report"]["mode"] == "format"
    assert got["report"]["summary"]["errors"] == 0


def test_validation_before_queue(client, queue):
    reg(client)
    big = b"PK" + b"0" * (20 * 1024 * 1024 + 1)
    cases = [
        (post(client), "Загрузите файл или вставьте текст"),
        (
            post(client, data={"text": "x"}, files={"file": ("a.docx", bad_docx(), DOCX_TYPE)}),
            "Загрузите файл или вставьте текст",
        ),
        (upload(client, big), "Файл больше 20 МБ"),
        (upload(client, b"garbage"), "Файл не похож на документ Word (.docx)"),
        (post(client, data={"text": "  \n "}), "Текст пустой — вставьте текст работы"),
    ]
    for resp, msg in cases:
        assert resp.status_code == 400 and resp.json()["detail"] == msg
    assert queue.count == 0 and len(queue.connection.keys("*")) == 0
    assert client.get("/jobs").json() == []
    assert post(client, data={"text": "abc", "profile_id": "nope"}).status_code == 404


def test_other_user_job_404(client, queue):
    reg(client, "a@example.com")
    jid = upload(client, bad_docx()).json()["id"]
    client.post("/auth/logout")
    reg(client, "b@example.com")
    for suffix in ("", "/docx", "/pdf"):
        assert client.get(f"/jobs/{jid}{suffix}").status_code == 404
    assert client.get("/jobs").json() == []
    # чужой профиль тоже 404
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "a@example.com", "password": "password1"})
    own = make_own(client)
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "b@example.com", "password": "password1"})
    assert post(client, data={"text": "abc", "profile_id": own["id"]}).status_code == 404


def test_snapshot_survives_profile_change(client, deferred_queue, db_session):
    reg(client)
    own = make_own(client, "Снимок")
    jid = post(client, data={"text": "Текст", "profile_id": own["id"]}).json()["id"]
    assert client.get(f"/jobs/{jid}").json()["status"] == "queued"
    client.put(f"/profiles/{own['id']}", json={"name": "Другое"})
    assert client.delete(f"/profiles/{own['id']}").status_code in (200, 204)
    worker.run_job(jid)
    got = client.get(f"/jobs/{jid}").json()
    assert got["status"] == "done", got
    assert got["report"]["profile"] == own["id"]
    assert client.get("/jobs").json()[0]["profile_name"] == "Снимок"


def test_engine_failure_sets_error(client, deferred_queue, monkeypatch):
    reg(client)
    jid = post(client, data={"text": "Текст"}).json()["id"]

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(worker, "process", boom)
    worker.run_job(jid)
    got = client.get(f"/jobs/{jid}").json()
    assert got["status"] == "error" and got["error"] == GENERIC

    jid2 = post(client, data={"text": "Текст"}).json()["id"]

    def changed(*a, **k):
        raise TextChangedError("x")

    monkeypatch.setattr(worker, "process", changed)
    worker.run_job(jid2)
    got = client.get(f"/jobs/{jid2}").json()
    assert got["status"] == "error"
    assert got["error"] == (
        "Обработка остановлена: оформление затронуло бы текст работы. Попробуйте режим «Проверить»."
    )


@pytest.mark.parametrize("exc", [PdfError("x"), OSError("cleanup")])
def test_pdf_failure_keeps_docx(client, queue, monkeypatch, exc):
    def fail(*a, **k):
        raise exc

    monkeypatch.setattr(worker, "render_pdf", fail)
    reg(client)
    jid = upload(client, bad_docx()).json()["id"]
    got = client.get(f"/jobs/{jid}").json()
    assert got["status"] == "done" and got["has_pdf"] is False
    assert "PDF-предпросмотр недоступен" in got["report"]["warnings"]
    assert client.get(f"/jobs/{jid}/docx").status_code == 200
    assert client.get(f"/jobs/{jid}/pdf").status_code == 404


def test_timeout_sets_error(client, deferred_queue):
    reg(client)
    jid = post(client, data={"text": "Текст"}).json()["id"]
    on_job_failure(SimpleNamespace(id=jid), None, JobTimeoutException, JobTimeoutException(), None)
    got = client.get(f"/jobs/{jid}").json()
    assert got["status"] == "error" and got["error"] == "Обработка заняла слишком много времени"
    # завершённую задачу не трогаем
    worker.run_job(jid)  # error не перезапускается
    on_job_failure(SimpleNamespace(id=jid), None, RuntimeError, RuntimeError(), None)
    assert client.get(f"/jobs/{jid}").json()["error"] == "Обработка заняла слишком много времени"


def test_not_ready_and_expired(client, deferred_queue, db_session):
    reg(client)
    jid = post(client, data={"text": "Текст"}).json()["id"]
    assert client.get(f"/jobs/{jid}/docx").status_code == 409
    job = db_session.get(Job, jid)
    job.status = "expired"
    db_session.commit()
    r = client.get(f"/jobs/{jid}/docx")
    assert r.status_code == 410 and r.json()["detail"] == "Срок хранения файла истёк"


def test_enqueue_options(client, deferred_queue):
    reg(client)
    jid = post(client, data={"text": "Текст"}).json()["id"]
    job = deferred_queue.fetch_job(jid)
    assert job.timeout == 120 and job.failure_callback
    json.dumps(client.get("/jobs").json())


def test_real_timeout_in_process_sets_timeout_error(client, deferred_queue, monkeypatch):
    reg(client)
    jid = post(client, data={"text": "Текст"}).json()["id"]

    def slow(*a, **k):
        raise JobTimeoutException("t")

    monkeypatch.setattr(worker, "process", slow)
    worker.run_job(jid)
    got = client.get(f"/jobs/{jid}").json()
    assert got["status"] == "error" and got["error"] == "Обработка заняла слишком много времени"


def test_timeout_in_pdf_keeps_docx(client, queue, monkeypatch):
    def slow(*a, **k):
        raise JobTimeoutException("t")

    monkeypatch.setattr(worker, "render_pdf", slow)
    reg(client)
    jid = upload(client, bad_docx()).json()["id"]
    got = client.get(f"/jobs/{jid}").json()
    assert got["status"] == "done" and got["has_pdf"] is False
    assert "PDF-предпросмотр недоступен" in got["report"]["warnings"]
    assert client.get(f"/jobs/{jid}/docx").status_code == 200


def test_missing_result_file_404_and_enqueue_failure_cleans(client, queue, monkeypatch, settings):
    import os

    reg(client)
    jid = upload(client, bad_docx()).json()["id"]
    os.remove(client.app.state.sessionmaker().get(Job, jid).output_docx)
    r = client.get(f"/jobs/{jid}/docx")
    assert r.status_code == 404 and r.json()["detail"] == "Файл результата не найден"

    def down(*a, **k):
        raise ConnectionError("redis")

    monkeypatch.setattr(queue, "enqueue", down)
    before = set(os.listdir(os.path.join(settings.storage_dir, "jobs")))
    assert post(client, data={"text": "abc"}).status_code == 503
    assert set(os.listdir(os.path.join(settings.storage_dir, "jobs"))) == before


@pytest.mark.parametrize(("job_timeout", "expected"), [(120, 60), (30, 15), (10, 10), (500, 60)])
def test_pdf_timeout_is_half_of_job_timeout(client, queue, monkeypatch, job_timeout, expected):
    from dataclasses import replace

    seen = {}

    def fake(docx_path, out_dir, *, soffice, timeout_s):
        seen["t"] = timeout_s
        out = out_dir / (docx_path.stem + ".pdf")
        out.write_bytes(b"%PDF-1.4")
        return out

    monkeypatch.setattr(worker, "render_pdf", fake)
    original = worker.get_settings
    monkeypatch.setattr(
        worker, "get_settings", lambda: replace(original(), job_timeout_s=job_timeout)
    )
    reg(client)
    upload(client, bad_docx())
    assert seen["t"] == expected


def test_text_field_over_1mb_is_russian_400(client):
    reg(client)
    r = client.post(
        "/jobs",
        data={"profile_id": GOST, "mode": "check", "text": "а" * (1024 * 1024 + 10)},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Неверные данные формы"
