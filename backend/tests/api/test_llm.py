import json

import httpx
import pytest

from gostdoc_api.config import Settings
from gostdoc_api.llm import LlmError, chat_json

S = Settings(
    database_url="sqlite://",
    redis_url="redis://x",
    storage_dir="/tmp/x",
    llm_api_key="sk-test",
    llm_base_url="https://llm.example/v1",
    llm_model="glm-4.5-flash",
)


def _transport(responses, seen):
    it = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return next(it)

    return httpx.MockTransport(handler)


def _ok(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_request_shape():
    seen = []
    out = chat_json("sys", "usr", settings=S, transport=_transport([_ok('{"a": 1}')], seen))
    assert out == {"a": 1}
    req = seen[0]
    assert str(req.url) == "https://llm.example/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer sk-test"
    body = json.loads(req.content)
    assert body["model"] == "glm-4.5-flash"
    assert body["temperature"] == 0
    assert body["thinking"] == {"type": "disabled"}
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]


def test_retry_on_500():
    seen = []
    tr = _transport([httpx.Response(500), _ok("{}")], seen)
    assert chat_json("s", "u", settings=S, transport=tr) == {}
    assert len(seen) == 2


def test_two_invalid_json():
    seen = []
    tr = _transport([_ok("не json"), _ok("снова не json")], seen)
    with pytest.raises(LlmError):
        chat_json("s", "u", settings=S, transport=tr)
    assert len(seen) == 2


def test_401_no_retry():
    seen = []
    with pytest.raises(LlmError):
        chat_json("s", "u", settings=S, transport=_transport([httpx.Response(401)], seen))
    assert len(seen) == 1


def test_429_retried():
    seen = []
    tr = _transport([httpx.Response(429), _ok("{}")], seen)
    chat_json("s", "u", settings=S, transport=tr)
    assert len(seen) == 2


def test_fenced_json():
    tr = _transport([_ok('```json\n{"x": [1]}\n```')], [])
    assert chat_json("s", "u", settings=S, transport=tr) == {"x": [1]}


def test_non_object_is_error():
    tr = _transport([_ok("[1]"), _ok("[1]")], [])
    with pytest.raises(LlmError):
        chat_json("s", "u", settings=S, transport=tr)


def _429(retry_after=None):
    return httpx.Response(429, headers={"Retry-After": retry_after} if retry_after else {})


def test_429_backoff_5_15_30():
    seen, sleeps = [], []
    tr = _transport([_429(), _429(), _429(), _ok("{}")], seen)
    assert chat_json("s", "u", settings=S, transport=tr, sleep=sleeps.append) == {}
    assert len(seen) == 4 and sleeps == [5, 15, 30]


def test_429_gives_up_after_three_retries():
    seen, sleeps = [], []
    tr = _transport([_429()] * 4, seen)
    with pytest.raises(LlmError):
        chat_json("s", "u", settings=S, transport=tr, sleep=sleeps.append)
    assert len(seen) == 4 and sleeps == [5, 15, 30]


def test_429_respects_retry_after_capped():
    seen, sleeps = [], []
    tr = _transport([_429("7"), _429("999"), _ok("{}")], seen)
    chat_json("s", "u", settings=S, transport=tr, sleep=sleeps.append)
    assert sleeps == [7, 30]


def test_429_bad_retry_after_falls_back():
    sleeps = []
    tr = _transport([_429("soon"), _ok("{}")], [])
    chat_json("s", "u", settings=S, transport=tr, sleep=sleeps.append)
    assert sleeps == [5]


def test_other_errors_single_retry_no_sleep_budget_shared():
    seen, sleeps = [], []
    tr = _transport([httpx.Response(500), httpx.Response(500)], seen)
    with pytest.raises(LlmError):
        chat_json("s", "u", settings=S, transport=tr, sleep=sleeps.append)
    assert len(seen) == 2 and sleeps == []


def test_extraction_timeout_covers_worst_case():
    from gostdoc_api.llm import extraction_timeout_s

    assert extraction_timeout_s(S) >= S.llm_timeout_s * 5 + 50
