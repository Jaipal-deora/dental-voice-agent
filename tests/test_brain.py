from pathlib import Path

import pytest
from fakes import ScriptedLLM, call

from dental_agent.messages import msg
from dental_agent.testing import make_memory_maker
from dental_agent.voice import brain
from dental_agent.voice.brain import Brain


async def test_handoff_ends_the_turn_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(brain, "EVENTS", tmp_path / "events.jsonl")
    b = Brain(
        ScriptedLLM([call("handoff_to_human", reason="asked")]),
        await make_memory_maker(),
    )
    assert await b.reply("I want to speak to a person") == msg("handoff")
    assert b.conv.status == "escalated"
    assert "handoff" in (tmp_path / "events.jsonl").read_text()
    assert await b.reply("hello?") == msg("closed")
