from datetime import date
from typing import Any

import pytest
from fakes import LoopingLLM, ScriptedLLM, call, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dental_agent import reliability
from dental_agent.agent import run_turn
from dental_agent.backends import FallbackLLM, ModelReply
from dental_agent.config import settings
from dental_agent.conversation import Conversation
from dental_agent.testing import make_memory_maker

TODAY = date(2030, 1, 6)
Maker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def maker() -> Maker:
    return await make_memory_maker(preload=True)


@pytest.fixture
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reliability, "BACKOFF_BASE", 0.0)
    monkeypatch.setattr(settings, "agent_timeout_s", 0.1)


class Dead:
    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelReply:
        raise TimeoutError


async def test_cancel_need_a_confirmation_turn(maker: Maker) -> None:
    conv = Conversation()
    llm = ScriptedLLM([call("cancel", appointment_id=1), text("Cancel Monday 9:00?")])
    async with maker() as s:
        await run_turn(conv, "Cancel my appointment", s, llm, TODAY)
        assert conv.pending is not None and conv.events == []

        llm.replies += [call("confirm_pending", confirmed=True), text("Cancelled.")]
        await run_turn(conv, "Yes", s, llm, TODAY)
    assert conv.events == ["cancelled"] and conv.outcome() == "cancelled"


async def test_model_cannot_confirm_for_the_caller(maker: Maker) -> None:
    conv = Conversation()
    llm = ScriptedLLM(
        [
            call("cancel", appointment_id=1),
            call("confirm_pending", confirmed=True),
            text("ok"),
        ]
    )

    async with maker() as s:
        await run_turn(conv, "Cancel my appointment", s, llm, TODAY)
    assert conv.events == []


async def test_tool_call_cap(maker: Maker) -> None:
    conv = Conversation()
    async with maker() as s:
        await run_turn(conv, "hi", s, LoopingLLM(call("get_hours")), TODAY)

    assert conv.status == "closed" and conv.tool_calls_used == settings.max_tool_calls


async def test_token_cap(maker: Maker) -> None:
    conv = Conversation()
    llm = LoopingLLM(call("get_hours", tokens=settings.max_conversation_tokens))
    async with maker() as s:
        await run_turn(conv, "hi", s, llm, TODAY)

    assert conv.status == "closed" and conv.tool_calls_used == 1


async def test_fallback_to_cheaper_model(fast: None) -> None:
    r = await FallbackLLM([Dead(), ScriptedLLM([text("from backup")])]).complete(
        "s", [], []
    )
    assert r.text == "from backup" and not r.degraded


async def test_scripted_reply_when_every_model_fails(fast: None) -> None:
    assert (await FallbackLLM([Dead(), Dead()]).complete("s", [], [])).degraded


async def test_retries_stop_at_three(fast: None) -> None:
    n = 0

    async def flaky() -> int:
        nonlocal n
        n += 1
        raise TimeoutError

    with pytest.raises(TimeoutError):
        await reliability.call_with_retries(flaky, timeout=0.1)

    assert n == 3
