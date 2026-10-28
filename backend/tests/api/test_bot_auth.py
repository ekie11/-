from pathlib import Path
from urllib.parse import quote

import pytest
from sqlalchemy import select

from gostdoc_api.config import get_settings
from gostdoc_api.models import Job, User

from .test_jobs import fake_pdf, post, queue, redis_conn  # noqa: F401
from .test_profiles import reg

SECRET = "s3cret-value"
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def bot_env(monkeypatch):
    monkeypatch.setenv("BOT_API_SECRET", SECRET)
    get_settings.cache_clear()


def hdr(uid="42", secret=SECRET, name=None):
    h = {"X-Bot-Secret": secret, "X-Telegram-User": uid}
    if name is not None:
        h["X-Telegram-Name"] = quote(name)  # заголовки только latin-1: имя в процент-кодировке
    return h


def test_bot_autocreates_user(client, db_session):
    r = client.get("/auth/me", headers=hdr("42", name="Иван"))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] is None and body["telegram_linked"] is True
    assert body["telegram_name"] == "Иван"
    u = db_session.scalars(select(User)).one()
    assert u.telegram_id == 42 and u.email is None and u.password_hash is None


def test_bot_same_user_again(client, db_session):
    a = client.get("/auth/me", headers=hdr("42")).json()
    b = client.get("/auth/me", headers=hdr("42", name="Новое")).json()
    assert a["id"] == b["id"] and b["telegram_name"] == "Новое"
    assert client.get("/auth/me", headers=hdr("43")).json()["id"] != a["id"]


@pytest.mark.parametrize("secret", ["", "wrong"])
def test_bad_secret_401(client, secret):
    assert client.get("/auth/me", headers=hdr(secret=secret)).status_code == 401


def test_empty_server_secret_disables_bot(client, monkeypatch):
    monkeypatch.setenv("BOT_API_SECRET", "")
    get_settings.cache_clear()
    client.app.state.settings = get_settings()
    assert client.get("/auth/me", headers=hdr(secret="")).status_code == 401


@pytest.mark.parametrize("uid", ["abc", "-1", "0", "", "1.5"])
def test_bad_telegram_id_401(client, uid):
    assert client.get("/auth/me", headers=hdr(uid)).status_code == 401


def test_no_headers_unchanged(client):
    assert client.get("/auth/me").status_code == 401


def test_bot_job_isolated(client, queue):  # noqa: F811
    r = post(client, data={"text": "Текст.", "mode": "format"}, headers=hdr("1"))
    assert r.status_code == 202
    assert [j["id"] for j in client.get("/jobs", headers=hdr("1")).json()] == [r.json()["id"]]
    assert client.get("/jobs", headers=hdr("2")).json() == []
    assert client.get(f"/jobs/{r.json()['id']}", headers=hdr("2")).status_code in (403, 404)


def test_bot_job_not_guest(client, queue, db_session):  # noqa: F811
    r = post(client, data={"text": "Текст.", "mode": "format"}, headers=hdr("1"))
    assert r.status_code == 202
    job = db_session.scalars(select(Job)).one()
    assert job.user_id is not None and job.guest_id is None
    assert "guest" not in client.cookies


def test_bot_header_beats_foreign_cookie(client, db_session):
    reg(client, "other@example.com")  # cookie чужой сессии
    other = client.get("/auth/me").json()
    me = client.get("/auth/me", headers=hdr("77")).json()
    assert me["id"] != other["id"] and me["email"] is None
    assert client.get("/profiles", headers=hdr("77")).status_code == 200


def test_login_empty_email_no_500(client, db_session):
    client.get("/auth/me", headers=hdr("42"))  # пользователь с email=NULL
    for email in ["", "   ", "null", "None"]:
        r = client.post("/auth/login", json={"email": email, "password": "password1"})
        assert r.status_code in (401, 422), email


def test_login_user_without_password_hash(client, db_session):
    db_session.add(User(email="x@example.com", password_hash=None))
    db_session.commit()
    r = client.post("/auth/login", json={"email": "x@example.com", "password": "password1"})
    assert r.status_code == 401


def test_me_email_user(client):
    reg(client)
    assert client.get("/auth/me").json() == {
        "id": 1,
        "email": "a@example.com",
        "telegram_name": None,
        "telegram_linked": False,
    }


def test_config_with_and_without_token(client, monkeypatch):
    assert client.get("/config").json() == {"telegram_bot_username": None}
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "gostdoc_bot")
    get_settings.cache_clear()
    client.app.state.settings = get_settings()
    assert client.get("/config").json() == {"telegram_bot_username": "gostdoc_bot"}
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "")
    get_settings.cache_clear()
    client.app.state.settings = get_settings()
    assert client.get("/config").json() == {"telegram_bot_username": None}


def test_caddyfile_strips_bot_headers():
    text = (ROOT / "Caddyfile").read_text(encoding="utf-8")
    for name in ("X-Bot-Secret", "X-Telegram-User", "X-Telegram-Name"):
        assert text.count(f"request_header -{name}") == 2  # :80 и блок с доменом
