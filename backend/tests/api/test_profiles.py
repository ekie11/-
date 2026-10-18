import copy
import json

GOST = "gost-7.32-2017"
FORBIDDEN = "Готовый ГОСТ-профиль нельзя изменить — создайте свой на его основе"


def reg(client, email="a@example.com"):
    r = client.post("/auth/register", json={"email": email, "password": "password1"})
    assert r.status_code == 201


def make_own(client, name="Мой"):
    r = client.post("/profiles", json={"base_id": GOST, "name": name})
    assert r.status_code == 201
    return r.json()


def test_requires_auth(client):
    assert client.delete(f"/profiles/{GOST}").status_code == 401
    assert client.get(f"/profiles/{GOST}/export").status_code == 401
    assert client.post("/profiles", json={"base_id": GOST, "name": "x"}).status_code == 401
    assert client.get("/profiles/unknown-id").status_code == 404


def test_anonymous_lists_only_builtin(client):
    r = client.get("/profiles")
    assert r.status_code == 200
    items = r.json()
    assert items and all(i["readonly"] for i in items)
    assert items[0]["id"] == GOST


def test_anonymous_get_builtin_public(client):
    r = client.get(f"/profiles/{GOST}")
    assert r.status_code == 200 and r.json()["readonly"] is True
    assert "guest" not in client.cookies


def test_list_gost_first(client):
    reg(client)
    own = make_own(client)
    items = client.get("/profiles").json()
    assert items[0] == {"id": GOST, "name": "ГОСТ 7.32-2017", "base": None, "readonly": True}
    assert items[-1] == {"id": own["id"], "name": "Мой", "base": GOST, "readonly": False}


def test_get_gost_no_diff(client):
    reg(client)
    r = client.get(f"/profiles/{GOST}")
    assert r.status_code == 200
    assert r.json()["readonly"] is True
    assert not any(r.json()["diff"].values())


def test_create_from_base_and_diff(client):
    reg(client)
    own = make_own(client)
    assert own["readonly"] is False and own["base"] == GOST and own["id"] != GOST
    rules = copy.deepcopy(own["rules"])
    rules["body.font_size"]["value"]["target_pt"] = 12
    r = client.put(f"/profiles/{own['id']}", json={"rules": rules, "name": "Новый"})
    assert r.status_code == 200
    got = client.get(f"/profiles/{own['id']}").json()
    assert got["name"] == "Новый"
    assert got["rules"]["body.font_size"]["value"]["target_pt"] == 12
    assert got["diff"]["body.font_size"] is True
    assert [k for k, v in got["diff"].items() if v] == ["body.font_size"]


def test_create_without_base(client):
    reg(client)
    rules = client.get(f"/profiles/{GOST}").json()["rules"]
    r = client.post("/profiles", json={"name": "X", "rules": rules})
    assert r.status_code == 201
    assert r.json()["base"] is None and r.json()["readonly"] is False


def test_create_invalid(client):
    reg(client)
    assert client.post("/profiles", json={"base_id": GOST}).status_code == 400
    assert client.post("/profiles", json={"base_id": "nope", "name": "x"}).status_code == 404
    bad = {"nope.rule": {"value": {}, "severity": "error", "source": "x"}}
    assert client.post("/profiles", json={"name": "x", "rules": bad}).status_code == 400


def test_gost_put_delete_403(client):
    reg(client)
    assert client.put(f"/profiles/{GOST}", json={"name": "x"}).status_code == 403
    r = client.delete(f"/profiles/{GOST}")
    assert r.status_code == 403
    assert r.json() == {"detail": FORBIDDEN}


def test_delete_own(client):
    reg(client)
    own = make_own(client)
    assert client.delete(f"/profiles/{own['id']}").status_code == 204
    assert client.get(f"/profiles/{own['id']}").status_code == 404


def test_put_invalid_rules_400(client):
    reg(client)
    own = make_own(client)
    bad = {"nope.rule": {"value": {}, "severity": "error", "source": "x"}}
    assert client.put(f"/profiles/{own['id']}", json={"rules": bad}).status_code == 400


def test_other_user_404(client):
    reg(client, "a@example.com")
    own = make_own(client)
    client.post("/auth/logout")
    reg(client, "b@example.com")
    pid = own["id"]
    assert client.get(f"/profiles/{pid}").status_code == 404
    assert client.put(f"/profiles/{pid}", json={"name": "x"}).status_code == 404
    assert client.delete(f"/profiles/{pid}").status_code == 404
    assert client.get(f"/profiles/{pid}/export").status_code == 404
    assert [p["id"] for p in client.get("/profiles").json()] == [GOST]


def test_export_import_roundtrip(client):
    reg(client)
    own = make_own(client)
    r = client.get(f"/profiles/{own['id']}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert f'filename="{own["id"]}.json"' in r.headers["content-disposition"]
    imp = client.post("/profiles/import", files={"file": ("p.json", r.content)})
    assert imp.status_code == 201
    new = imp.json()
    assert new["id"] != own["id"] and new["readonly"] is False
    assert new["rules"] == own["rules"]


def test_import_gost_export_not_readonly(client):
    reg(client)
    r = client.get(f"/profiles/{GOST}/export")
    new = client.post("/profiles/import", files={"file": ("g.json", r.content)}).json()
    assert new["readonly"] is False and new["id"] != GOST and new["base"] is None


def test_import_broken_400(client):
    reg(client)
    r = client.post("/profiles/import", files={"file": ("p.json", b"{not json")})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Файл профиля повреждён: ")
    data = client.get(f"/profiles/{GOST}").json()
    data["rules"]["nope.rule"] = {"value": {}, "severity": "error", "source": "x"}
    r = client.post("/profiles/import", files={"file": ("p.json", json.dumps(data).encode())})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Файл профиля повреждён: ")
    r = client.post("/profiles/import", files={"file": ("p.json", b"\xff\xfe")})
    assert r.status_code == 400


def test_import_deeply_nested_400(client):
    reg(client)
    r = client.post("/profiles/import", files={"file": ("p.json", b"[" * 100000)})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Файл профиля повреждён: ")


def test_import_too_large_400(client):
    reg(client)
    r = client.post("/profiles/import", files={"file": ("p.json", b" " * (1024 * 1024 + 1))})
    assert r.status_code == 400
    assert r.json()["detail"] == "Файл профиля слишком большой"


def test_resolve_profile(client, db_session):
    from gostdoc_api.models import User
    from gostdoc_api.profiles_service import resolve_profile

    reg(client)
    own = make_own(client)
    user = db_session.query(User).one()
    assert resolve_profile(db_session, user, GOST).id == GOST
    assert resolve_profile(db_session, user, own["id"]).base == GOST
    import pytest

    with pytest.raises(LookupError):
        resolve_profile(db_session, user, "zzz")
