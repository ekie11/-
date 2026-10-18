from sqlalchemy import select

from gostdoc_api.models import SessionToken, User


def reg(client, email="u@example.com", password="password1"):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_register_and_me(client):
    r = reg(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "u@example.com"
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json() == body


def test_email_normalized(client):
    r = reg(client, " A@B.ru ")
    assert r.status_code == 201
    assert r.json()["email"] == "a@b.ru"


def test_duplicate_409(client):
    reg(client)
    r = reg(client, "U@Example.com")
    assert r.status_code == 409
    assert r.json() == {"detail": "Этот email уже зарегистрирован"}


def test_short_password_400(client):
    r = reg(client, password="short")
    assert r.status_code == 400
    assert r.json() == {"detail": "Пароль должен быть не короче 8 символов"}


def test_bad_email_400(client):
    r = reg(client, email="nope")
    assert r.status_code == 400
    assert r.json() == {"detail": "Неверный email"}


def test_missing_body_400(client):
    r = client.post("/auth/register", json={})
    assert r.status_code == 400
    assert isinstance(r.json()["detail"], str)


def test_login_failures_identical(client):
    reg(client)
    client.cookies.clear()
    a = client.post("/auth/login", json={"email": "u@example.com", "password": "wrongpass1"})
    b = client.post("/auth/login", json={"email": "x@example.com", "password": "wrongpass1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json() == {"detail": "Неверный email или пароль"}


def test_login_ok(client):
    reg(client)
    client.cookies.clear()
    r = client.post("/auth/login", json={"email": "U@example.com", "password": "password1"})
    assert r.status_code == 200
    assert client.get("/auth/me").status_code == 200


def test_me_unauthenticated(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "Нужно войти"}


def test_logout_invalidates_old_cookie(client, db_session):
    reg(client)
    old = client.cookies.get("session")
    assert old
    r = client.post("/auth/logout")
    assert r.status_code == 204
    assert db_session.scalars(select(SessionToken)).all() == []
    client.cookies.clear()
    client.cookies.set("session", old)
    assert client.get("/auth/me").status_code == 401


def test_only_hash_stored(client, db_session):
    reg(client)
    token = client.cookies.get("session")
    rows = db_session.scalars(select(SessionToken)).all()
    assert len(rows) == 1
    assert rows[0].token_hash != token
    assert token not in rows[0].token_hash
    assert len(rows[0].token_hash) == 64
    user = db_session.scalars(select(User)).one()
    assert "password1" not in user.password_hash


def test_cookie_flags(client):
    r = reg(client)
    c = r.headers["set-cookie"].lower()
    assert "httponly" in c
    assert "samesite=lax" in c
    assert "session=" in c


def test_expired_session_invalid(client, db_session):
    from datetime import UTC, datetime, timedelta

    reg(client)
    row = db_session.scalars(select(SessionToken)).one()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert client.get("/auth/me").status_code == 401


def test_hash_verify():
    from gostdoc_api.auth import hash_password, verify_password

    h = hash_password("password1")
    assert verify_password(h, "password1")
    assert not verify_password(h, "other")
    assert not verify_password("garbage", "password1")
