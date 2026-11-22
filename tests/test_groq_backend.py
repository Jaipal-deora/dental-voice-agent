from types import SimpleNamespace
from typing import Any

import pytest

from dental_agent import backends
from dental_agent.backends import GroqBackend, _to_openai


def test_stored_messages_become_openai_messages() -> None:
    msgs: list[dict[str, Any]] = [
        {"role": "user", "content": "cancel it"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "cancel",
                    "input": {"appointment_id": 1},
                }
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{}"}],
        },
    ]
    out = _to_openai("sys", msgs)
    assert [m["role"] for m in out] == ["system", "user", "assistant", "tool"]
    assert out[2]["tool_calls"][0]["function"]["arguments"] == '{"appointment_id": 1}'
    assert out[3]["tool_call_id"] == "t1"


async def test_backend_parses_a_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    fn = SimpleNamespace(name="cancel", arguments='{"appointment_id": 1}')
    tc = SimpleNamespace(id="t1", type="function", function=fn)
    choice = SimpleNamespace(
        finish_reason="tool_calls",
        message=SimpleNamespace(content=None, tool_calls=[tc]),
    )
    resp = SimpleNamespace(choices=[choice], usage=SimpleNamespace(total_tokens=42))

    async def fake(**kwargs: Any) -> Any:
        return resp

    monkeypatch.setattr(backends.client.chat.completions, "create", fake)
    r = await GroqBackend("openai/gpt-oss-20b").complete(
        "s", [{"role": "user", "content": "hi"}], []
    )
    assert r.tool_calls[0].input == {"appointment_id": 1} and r.tokens == 42


async def test_truncated_reply_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    choice = SimpleNamespace(
        finish_reason="length", message=SimpleNamespace(content="", tool_calls=None)
    )

    async def fake(**kwargs: Any) -> Any:
        return SimpleNamespace(choices=[choice], usage=None)

    monkeypatch.setattr(backends.client.chat.completions, "create", fake)
    with pytest.raises(TimeoutError):
        await GroqBackend("openai/gpt-oss-20b").complete(
            "s", [{"role": "user", "content": "hi"}], []
        )
