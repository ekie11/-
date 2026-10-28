import pytest
from pydantic import ValidationError

from gostdoc_engine.profile import KNOWN_RULE_KEYS, Profile, builtin_profile


def test_builtin_gost_732_loads():
    p = builtin_profile("gost-7.32-2017")
    assert p.readonly is True
    assert p.rules["page.margins"].value == {
        "top_mm": 20, "bottom_mm": 20, "left_mm": 30, "right_mm": 15,
    }
    assert p.rules["body.font_size"].value["min_pt"] == 12
    assert set(p.rules) == KNOWN_RULE_KEYS


def test_unknown_rule_key_rejected():
    with pytest.raises(ValidationError):
        Profile(id="x", name="x", base=None, readonly=False,
                rules={"nope.rule": {"value": {}, "severity": "error", "source": ""}})


def test_bad_severity_rejected():
    with pytest.raises(ValidationError):
        Profile(id="x", name="x", base=None, readonly=False,
                rules={"page.size": {"value": {}, "severity": "fatal", "source": ""}})
