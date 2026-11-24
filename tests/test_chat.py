from fakes import ScriptedLLM, call, text
from httpx import AsyncClient

from dental_agent.api import get_llm
from dental_agent.main import app


def use_llm(llm: ScriptedLLM) -> None:
    app.dependency_overrides[get_llm] = lambda: llm


async def test_chat_endpoint(client: AsyncClient) -> None:
    use_llm(ScriptedLLM([text("Hello!")]))
    r = await client.post("/chat", json={"text": "hi"})
    assert r.status_code == 200
    assert r.json()["reply"] == "Hello!"
    assert r.json()["status"] == "active"
    assert r.json()["conversation_id"]


async def test_second_turn_keeps_the_conversation(client: AsyncClient) -> None:
    use_llm(ScriptedLLM([text("Hello!"), text("Which day suits you?")]))
    first = (await client.post("/chat", json={"text": "hi"})).json()
    second = await client.post(
        "/chat",
        json={"conversation_id": first["conversation_id"], "text": "I need a clean"},
    )
    assert second.json()["conversation_id"] == first["conversation_id"]
    assert second.json()["reply"] == "Which day suits you?"


async def test_handoff_closes_the_conversation(client: AsyncClient) -> None:
    use_llm(ScriptedLLM([call("handoff_to_human", reason="asked")]))
    r = await client.post("/chat", json={"text": "I want to speak to a person"})
    assert r.json()["status"] == "escalated"


async def test_empty_text_is_rejected(client: AsyncClient) -> None:
    r = await client.post("/chat", json={"text": ""})
    assert r.status_code == 422
