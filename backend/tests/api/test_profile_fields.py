import pytest
from fastapi.testclient import TestClient

from gostdoc_api import fields
from gostdoc_api.app import create_app
from gostdoc_api.config import get_settings
from gostdoc_api.models import Base
from gostdoc_engine.profile import list_builtin_profiles

PROFILES = [(p.id, p) for p in list_builtin_profiles()]


def leaves(v, prefix=""):
    if isinstance(v, dict):
        return [x for k, s in v.items() for x in leaves(s, f"{prefix}.{k}" if prefix else k)]
    return [prefix]


def at(v, path):
    for k in path.split("."):
        if not isinstance(v, dict) or k not in v:
            return None
        v = v[k]
    return v


def test_profile_fields_endpoint(client):
    r = client.get("/profile-fields")
    assert r.status_code == 200
    data = r.json()
    assert [g["label"] for g in data["groups"]] == [
        "Страница", "Основной текст", "Заголовки", "Структура", "Нумерация страниц",
        "Рисунки и таблицы", "Формулы", "Списки", "Источники", "Типографика",
    ]  # fmt: skip
    assert data["rule_labels"]["page.margins"] == "Поля"
    assert any(f["rule"] == "page.margins" and f["path"] == "top_mm" for f in data["fields"])
    assert data["extraction_enabled"] is False


def test_extraction_enabled_with_key(settings, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app(get_settings())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as c:
        assert c.get("/profile-fields").json()["extraction_enabled"] is True


def test_fields_json_is_not_a_profile(client):
    ids = [p["id"] for p in client.get("/profiles").json()]
    assert "fields" not in ids
    assert client.get("/profiles/fields").status_code == 404


def test_groups_exist_and_kinds_valid():
    data = fields.load_fields()
    group_ids = {g["id"] for g in data["groups"]}
    for f in data["fields"]:
        assert f["group"] in group_ids
        assert f["kind"] in {"number", "select", "bool", "text", "fixed"}


@pytest.mark.parametrize(("pid", "profile"), PROFILES)
def test_every_field_points_to_existing_path(pid, profile):
    rules = profile.model_dump()["rules"]
    for rule, path in fields.field_index():
        assert rule in rules, rule
        assert at(rules[rule]["value"], path) is not None, f"{rule}.{path}"


@pytest.mark.parametrize(("pid", "profile"), PROFILES)
def test_every_leaf_is_described(pid, profile):
    index = fields.field_index()
    for rule, cfg in profile.model_dump()["rules"].items():
        for leaf in leaves(cfg["value"]):
            assert (rule, leaf) in index, f"{rule}.{leaf}"


@pytest.mark.parametrize(("pid", "profile"), PROFILES)
def test_value_type_matches_kind(pid, profile):
    rules = profile.model_dump()["rules"]
    for f in fields.load_fields()["fields"]:
        v = at(rules[f["rule"]]["value"], f["path"])
        if f["kind"] == "number":
            assert isinstance(v, int | float) and not isinstance(v, bool)
        if f["kind"] == "bool":
            assert isinstance(v, bool)
        if f["kind"] == "text":
            assert isinstance(v, str)
        if f["kind"] in {"select", "fixed"}:
            sv = str(v).lower() if isinstance(v, bool) else str(v)
            assert sv in [o["value"] for o in f["options"]]


def test_fixed_fields():
    fixed = sorted(
        f"{f['rule']}.{f['path']}={f['options'][0]['value']}"
        for f in fields.load_fields()["fields"]
        if f["kind"] == "fixed"
    )
    assert fixed == [
        "bibliography.citation_format=[N]",
        "bibliography.order=mention",
        "bibliography.standard=7.0.100-2018",
        "captions.figure.position=below",
        "captions.table.position=above",
        "headings.section.trailing_period=false",
        "headings.structural.trailing_period=false",
        "page.size.format=A4",
        "toc.hyperlinks=true",
        "toc.levels=3",
    ]
