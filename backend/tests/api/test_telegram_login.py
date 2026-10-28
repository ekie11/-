import hashlib
import hmac
import time

import pytest
from sqlalchemy import select

from gostdoc_api.config import get_settings
from gostdoc_api.models import User
from gostdoc_api.telegram_login import TelegramAuthError, verify

from .test_bot_auth import hdr
from .test_guest import gpost
from .test_jobs import fake_pdf, queue, redis_conn  # noqa: F401
from .test_profiles import reg

TOKEN = "123456:TEST-token"


@pytest.fixture(autouse=True)
def tg_env(monkeypatch):
    monkeypatch.setenv("BOT_API_SECRET", "s3cret-value")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    get_settings.cache_clear()


def widget(tg_id=555, token=TOKEN, auth_date=None, **extra):
    data = {"id": tg_id, "first_name": "Иван", "auth_date": auth_date or int(time.time())}
    data.update(extra)
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(token.encode()).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return data


def test_verify_ok_and_optional_fields():
    now = int(time.time())
    d = widget(auth_date=now, last_name="Петров", username="ivan", photo_url="https://t.me/i/x.jpg")
    assert verify(d, TOKEN, now) == 555


@pytest.mark.parametrize("field", ["id", "first_name", "auth_date"])
def test_verify_tampered(field):
    now = int(time.time())
    d = widget(auth_date=now)
    d[field] = 999 if field != "first_name" else "Другой"
    with pytest.raises(TelegramAuthError):
        verify(d, TOKEN, now)


def test_verify_missing_hash_and_wrong_token():
    now = int(time.time())
    d = widget(auth_date=now)
    with pytest.raises(TelegramAuthError):
        verify({k: v for k, v in d.items() if k != "hash"}, TOKEN, now)
    with pytest.raises(TelegramAuthError):
        verify(d, "other:token", now)


def test_verify_stale():
    now = int(time.time())
    with pytest.raises(TelegramAuthError):
        verify(widget(auth_date=now - 86401), TOKEN, now)
    assert verify(widget(auth_date=now - 86400), TOKEN, now) == 555


def test_login_creates_user_and_session(client, db_session):
    r = client.post("/auth/telegram", json=widget(last_name="Петров"))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] is None and body["telegram_linked"] is True
    assert body["telegram_name"] == "Иван Петров"
    assert "session" in client.cookies
    assert client.get("/auth/me").json()["id"] == body["id"]
    assert db_session.scalars(select(User)).one().telegram_id == 555


def test_login_finds_existing_and_updates_name(client, db_session):
    a = client.post("/auth/telegram", json=widget()).json()
    client.post("/auth/logout")
    b = client.post("/auth/telegram", json=widget(last_name="Новый")).json()
    assert a["id"] == b["id"] and b["telegram_name"] == "Иван Новый"
    assert len(db_session.scalars(select(User)).all()) == 1


def test_login_bad_signature_401(client, db_session):
    d = widget()
    d["first_name"] = "Подделка"
    r = client.post("/auth/telegram", json=d)
    assert r.status_code == 401
    assert r.json()["detail"] == "Не удалось подтвердить вход через Telegram"
    assert "session" not in client.cookies
    assert db_session.scalars(select(User)).all() == []


def test_login_stale_401(client):
    r = client.post("/auth/telegram", json=widget(auth_date=int(time.time()) - 90000))
    assert r.status_code == 401


@pytest.mark.parametrize("body", [{}, {"id": "x", "auth_date": 1, "hash": "00"}, {"id": 1}])
def test_login_garbage_401(client, body):
    assert client.post("/auth/telegram", json=body).status_code == 401


def test_login_claims_guest_jobs(client, queue, db_session):  # noqa: F811
    gid = gpost(client).json()["id"]
    assert client.post("/auth/telegram", json=widget()).status_code == 200
    assert "guest" not in client.cookies
    assert [j["id"] for j in client.get("/jobs").json()] == [gid]


def test_bot_user_signs_in_with_widget(client, db_session):  # Review Focus 1
    bot_me = client.get("/auth/me", headers=hdr("555", name="Иван")).json()
    created = client.post(
        "/profiles", json={"base_id": "gost-7.32-2017", "name": "Из бота"}, headers=hdr("555")
    )
    assert created.status_code == 201
    r = client.post("/auth/telegram", json=widget(555))
    assert r.status_code == 200 and r.json()["id"] == bot_me["id"]
    names = [p["name"] for p in client.get("/profiles").json()]
    assert "Из бота" in names
    assert len(db_session.scalars(select(User)).all()) == 1


def test_link_success(client, db_session):
    reg(client)
    r = client.post("/auth/telegram/link", json=widget(777, first_name="Анна"))
    assert r.status_code == 200
    assert r.json()["telegram_linked"] is True and r.json()["email"] == "a@example.com"
    assert (
        db_session.scalars(select(User).where(User.email == "a@example.com")).one().telegram_id
        == 777
    )
    # повторная привязка того же Telegram идемпотентна
    assert client.post("/auth/telegram/link", json=widget(777)).status_code == 200


def test_link_taken_409(client, db_session):
    client.post("/auth/telegram", json=widget(777))
    client.post("/auth/logout")
    reg(client)
    r = client.post("/auth/telegram/link", json=widget(777))
    assert r.status_code == 409
    assert r.json()["detail"] == "Этот Telegram уже привязан к другому аккаунту"


def test_link_requires_login_and_valid_signature(client):
    assert client.post("/auth/telegram/link", json=widget()).status_code == 401
    reg(client)
    d = widget()
    d["id"] = 1
    assert client.post("/auth/telegram/link", json=d).status_code == 401


def test_no_token_503(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    get_settings.cache_clear()
    client.app.state.settings = get_settings()
    reg(client)
    for path in ("/auth/telegram", "/auth/telegram/link"):
        r = client.post(path, json=widget())
        assert r.status_code == 503 and r.json()["detail"] == "Функция не настроена"


@pytest.mark.parametrize("uid", [str(2**63), "9" * 20, "1" * 25])
def test_bot_telegram_id_too_big_401(client, uid):
    assert client.get("/auth/me", headers=hdr(uid)).status_code == 401


def test_bot_telegram_id_max_ok(client):
    assert client.get("/auth/me", headers=hdr(str(2**63 - 1))).status_code == 200
