import asyncio
import json
import time

import pytest
from httpx import AsyncClient

from dental_agent import llm

GOOD = json.dumps({
    "intent":"book",
    "day": "thursday",
    "daypart": "afternoon",
    "service": "clean",
    "confidence": 0.9
})

SENTENCE = {"text": "Can I come in Thursday afternoon for a clean?"}

@pytest.fixture(autouse=True)
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm,"BACKOFF_BASE", 0.0)
    monkeypatch.setattr(llm.settings,"llm_timeout_s",0.1)

async def test_valid_output(client: AsyncClient, monkeypatch:pytest.MonkeyPatch) -> None:
    async def fake(text:str) -> str:
        return GOOD 

    monkeypatch.setattr(llm,"_call_model",fake)
    r = await client.post("/parse",json=SENTENCE)
    assert r.status_code == 200 and r.json()["daypart"] == "afternoon"

async def test_malformed_output_retried_then_rejected(
        client: AsyncClient, monkeypatch:pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    async def fake(text:str)-> str:
        calls.append(text)
        return "not json"

    monkeypatch.setattr(llm,"_call_model",fake)
    r = await client.post("/parse",json=SENTENCE)
    assert r.status_code == 502 and len(calls) == 3 

async def test_timeout_returns_clean_error(
        client: AsyncClient, monkeypatch:pytest.MonkeyPatch
) -> None:
    async def hang(text:str) -> str:
        await asyncio.sleep(5)
        return GOOD 
    monkeypatch.setattr(llm,"_call_model",hang)
    t0 = time.monotonic()
    r = await client.post("/parse",json=SENTENCE)
    assert r.status_code == 502 and time.monotonic() - t0 < 2 

async def test_two_slow_calls_overlap(client:AsyncClient,monkeypatch:pytest.MonkeyPatch) -> None:
    async def slow(text:str) -> str:
        await asyncio.sleep(0.4)
        return GOOD 
    monkeypatch.setattr(llm,"_call_model",slow)
    monkeypatch.setattr(llm.settings,"llm_timeout_s",2.0)
    t0 = time.monotonic()
    await asyncio.gather(client.post("/parse",json=SENTENCE),client.post("/parse",json=SENTENCE))
    assert time.monotonic() - t0 < 0.7 
