from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from gostdoc_api.app import create_app
from gostdoc_api.cleanup import cleanup_expired
from gostdoc_api.client_ip import client_ip
from gostdoc_api.models import Base, GuestSession, Job

from .test_jobs import fake_pdf, post, queue, redis_conn  # noqa: F401
from .test_profiles import GOST, make_own, reg

LIMIT = "Зарегистрируйтесь, чтобы продолжить"


def gpost(client, text="Текст работы."):
    return post(client, data={"text": text, "mode": "format"})


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def test_guest_creates_job_cookie_and_hash(client, queue, db_session):  # noqa: F811
    r = gpost(client)
    assert r.status_code == 202
    token = client.cookies.get("guest")
    assert token
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    g = db_session.query(GuestSession).one()
    assert g.token_hash != token and len(g.token_hash) == 64
    delta = _aware(g.expires_at) - datetime.now(UTC)
    assert timedelta(hours=23, minutes=55) < delta <= timedelta(hours=24)
    job = db_session.get(Job, r.json()["id"])
    assert job.user_id is None and job.guest_id == g.id and job.client_ip
    assert abs(_aware(job.expires_at) - _aware(g.expires_at)) < timedelta(minutes=1)
    assert client.get(f"/jobs/{job.id}").json()["status"] == "done"
    assert client.get(f"/jobs/{job.id}/docx").status_code == 200
    assert len(client.get("/jobs").json()) == 1


def test_reads_without_cookie_do_not_mint_guest(client, db_session):
    r = client.get("/jobs")
    assert r.status_code == 401 and r.json()["detail"] == "Нужно войти"
    assert client.get("/jobs/x").status_code == 401
    assert "guest" not in client.cookies
    assert db_session.query(GuestSession).count() == 0


def test_expired_guest_is_absent(client, queue, db_session):  # noqa: F811
    gpost(client)
    g = db_session.query(GuestSession).one()
    g.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    assert client.get("/jobs").status_code == 401


def test_fourth_job_same_guest_429(client, queue):  # noqa: F811
    for _ in range(3):
        assert gpost(client).status_code == 202
    r = gpost(client)
    assert r.status_code == 429 and r.json()["detail"] == LIMIT


def test_ip_limit_survives_cookie_deletion(client, queue):  # noqa: F811
    for _ in range(10):
        client.cookies.clear()
        assert gpost(client).status_code == 202
    client.cookies.clear()
    assert gpost(client).status_code == 429
    # новый гость не видит старых задач
    assert client.get("/jobs").status_code == 401


def test_registered_not_limited(client, queue):  # noqa: F811
    reg(client)
    for _ in range(4):
        assert gpost(client).status_code == 202


def test_guests_isolated(client, queue):  # noqa: F811
    jid = gpost(client).json()["id"]
    client.cookies.clear()
    gpost(client)
    for suffix in ("", "/docx", "/pdf"):
        assert client.get(f"/jobs/{jid}{suffix}").status_code == 404
    assert len(client.get("/jobs").json()) == 1


def test_user_job_hidden_from_guest_and_back(client, queue):  # noqa: F811
    reg(client)
    uid = gpost(client).json()["id"]
    client.cookies.clear()
    gid = gpost(client).json()["id"]
    assert client.get(f"/jobs/{uid}").status_code == 404
    reg(client, "b@example.com")  # claims guest job
    assert client.get(f"/jobs/{gid}").status_code == 200
    assert client.get(f"/jobs/{uid}").status_code == 404


def test_guest_own_profile_404(client, queue):  # noqa: F811
    reg(client)
    own = make_own(client)
    client.cookies.clear()
    r = post(client, data={"text": "Текст.", "mode": "check", "profile_id": own["id"]})
    assert r.status_code == 404


def test_register_claims_only_own_jobs(client, queue, db_session, settings):  # noqa: F811
    mine = gpost(client).json()["id"]
    mine_cookie = client.cookies.get("guest")
    client.cookies.clear()
    other = gpost(client).json()["id"]
    client.cookies.clear()
    client.cookies.set("guest", mine_cookie, domain="testserver.local")
    r = client.post("/auth/register", json={"email": "n@example.com", "password": "password1"})
    assert r.status_code == 201
    assert "guest" not in client.cookies
    assert any(h.startswith("guest=") for h in r.headers.get_list("set-cookie"))
    db_session.expire_all()
    job = db_session.get(Job, mine)
    assert job.user_id is not None and job.guest_id is None
    delta = _aware(job.expires_at) - datetime.now(UTC)
    assert (
        timedelta(days=settings.file_ttl_days - 1) < delta <= timedelta(days=settings.file_ttl_days)
    )
    assert client.get(f"/jobs/{mine}/docx").status_code == 200
    assert [j["id"] for j in client.get("/jobs").json()] == [mine]
    other_job = db_session.get(Job, other)
    assert other_job.user_id is None and other_job.guest_id is not None
    assert db_session.query(GuestSession).count() == 1


def test_login_claims_only_cookie_guest_keeps_existing(client, queue, db_session):  # noqa: F811
    reg(client)
    old = gpost(client).json()["id"]
    client.post("/auth/logout")
    client.cookies.clear()
    stranger = gpost(client).json()["id"]
    client.cookies.clear()
    mine = gpost(client).json()["id"]
    r = client.post("/auth/login", json={"email": "a@example.com", "password": "password1"})
    assert r.status_code == 200
    ids = {j["id"] for j in client.get("/jobs").json()}
    assert ids == {old, mine}
    assert stranger not in ids


def test_login_with_guest_cookie_claims(client, queue, db_session):  # noqa: F811
    reg(client)
    client.post("/auth/logout")
    gid = gpost(client).json()["id"]
    r = client.post("/auth/login", json={"email": "a@example.com", "password": "password1"})
    assert r.status_code == 200
    assert "guest" not in client.cookies
    assert [j["id"] for j in client.get("/jobs").json()] == [gid]


def test_claim_skips_expired_jobs(client, queue, db_session):  # noqa: F811
    jid = gpost(client).json()["id"]
    job = db_session.get(Job, jid)
    job.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()
    reg(client)
    db_session.expire_all()
    assert db_session.get(Job, jid).user_id is None


def test_cleanup_removes_expired_guests(client, queue, db_session, settings):  # noqa: F811
    gpost(client)
    now = datetime.now(UTC)
    assert cleanup_expired(db_session, settings, now) == 0
    assert db_session.query(GuestSession).count() == 1
    cleanup_expired(db_session, settings, now + timedelta(hours=25))
    assert db_session.query(GuestSession).count() == 0


class Hdrs(dict):
    def getlist(self, key):
        v = self.get(key)
        return [] if v is None else (v if isinstance(v, list) else [v])


def req(peer, xff=None):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=Hdrs(headers))


def test_client_ip_rules():
    trusted = ("10.0.0.0/8", "192.168.1.1/32")
    assert client_ip(req("1.2.3.4", "9.9.9.9"), trusted) == "1.2.3.4"
    assert client_ip(req("10.0.0.1", "9.9.9.9"), ()) == "10.0.0.1"
    assert client_ip(req("10.0.0.1", "9.9.9.9"), trusted) == "9.9.9.9"
    # подделанный левый адрес игнорируется, берётся первый недоверенный справа
    assert client_ip(req("10.0.0.1", "6.6.6.6, 9.9.9.9, 10.0.0.2"), trusted) == "9.9.9.9"
    assert client_ip(req("10.0.0.1", "garbage, 10.0.0.2"), trusted) == "10.0.0.1"
    assert client_ip(req("10.0.0.1", "10.0.0.2"), trusted) == "10.0.0.1"
    assert client_ip(req("10.0.0.1"), trusted) == "10.0.0.1"
    assert client_ip(req("::1", "9.9.9.9"), trusted) == "::1"


def _app_with(settings, trusted, peer):
    app = create_app(replace(settings, trusted_proxies=trusted))
    Base.metadata.create_all(app.state.engine)
    return app, TestClient(app, client=(peer, 5000))


def test_xff_ignored_from_untrusted_peer(settings, redis_conn):  # noqa: F811
    from rq import Queue

    from gostdoc_api.queue import get_queue

    app, c = _app_with(settings, ("10.0.0.0/8",), "1.2.3.4")
    app.dependency_overrides[get_queue] = lambda: Queue(is_async=False, connection=redis_conn)
    with c:
        for i in range(10):
            c.cookies.clear()
            r = c.post(
                "/jobs",
                data={"profile_id": GOST, "mode": "format", "text": "Текст."},
                headers={"X-Forwarded-For": f"9.9.9.{i}"},
            )
            assert r.status_code == 202
        c.cookies.clear()
        r = c.post(
            "/jobs",
            data={"profile_id": GOST, "mode": "format", "text": "Текст."},
            headers={"X-Forwarded-For": "9.9.9.200"},
        )
        assert r.status_code == 429


def test_xff_used_from_trusted_peer(settings, redis_conn):  # noqa: F811
    from rq import Queue

    from gostdoc_api.queue import get_queue

    app, c = _app_with(settings, ("10.0.0.0/8",), "10.0.0.1")
    app.dependency_overrides[get_queue] = lambda: Queue(is_async=False, connection=redis_conn)
    with c:
        for i in range(10):
            c.cookies.clear()
            r = c.post(
                "/jobs",
                data={"profile_id": GOST, "mode": "format", "text": "Текст."},
                headers={"X-Forwarded-For": "9.9.9.9"},
            )
            assert r.status_code == 202
        c.cookies.clear()
        other = c.post(
            "/jobs",
            data={"profile_id": GOST, "mode": "format", "text": "Текст."},
            headers={"X-Forwarded-For": "8.8.8.8"},
        )
        assert other.status_code == 202
        c.cookies.clear()
        blocked = c.post(
            "/jobs",
            data={"profile_id": GOST, "mode": "format", "text": "Текст."},
            headers={"X-Forwarded-For": "9.9.9.9"},
        )
        assert blocked.status_code == 429


def test_client_ip_multiple_xff_lines():
    trusted = ("10.0.0.0/8",)
    r = req("10.0.0.1", ["6.6.6.6", "9.9.9.9, 10.0.0.2"])
    assert client_ip(r, trusted) == "9.9.9.9"


def test_invalid_anonymous_posts_create_no_guest(client, queue, db_session):  # noqa: F811
    r = post(client, data={"text": "", "mode": "format"})
    assert r.status_code == 400
    r = post(client, data={"text": "Т.", "mode": "format", "profile_id": "nope"})
    assert r.status_code == 404
    assert client.post("/jobs", data={"mode": "format"}).status_code in (400, 422)
    assert db_session.query(GuestSession).count() == 0
    assert "guest" not in client.cookies
    for _ in range(10):
        client.cookies.clear()
        assert gpost(client).status_code == 202
    n = db_session.query(GuestSession).count()
    client.cookies.clear()
    r = gpost(client)
    assert r.status_code == 429
    assert "set-cookie" not in r.headers and "guest" not in client.cookies
    assert db_session.query(GuestSession).count() == n


def test_valid_anonymous_post_creates_one_guest(client, queue, db_session):  # noqa: F811
    assert gpost(client).status_code == 202
    assert db_session.query(GuestSession).count() == 1


def test_guest_lists_only_builtin_profiles(client, queue):  # noqa: F811
    assert gpost(client).status_code == 202
    assert client.cookies.get("guest")
    r = client.get("/profiles")
    assert r.status_code == 200
    items = r.json()
    assert items and all(i["readonly"] for i in items)
    assert client.get(f"/profiles/{GOST}").status_code == 200
