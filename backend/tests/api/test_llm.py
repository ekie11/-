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
    llm_model="glm-4.6",
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
    assert body["model"] == "glm-4.6"
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
