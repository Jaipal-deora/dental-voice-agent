import json
import time
from datetime import date
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dental_agent import agent
from dental_agent.backends import Backend, build_llm
from dental_agent.conversation import Conversation
from dental_agent.db import SessionLocal

EVENTS = Path("logs/events.jsonl")


def log_event(kind: str, **data: object) -> None:
    EVENTS.parent.mkdir(exist_ok=True)
    with EVENTS.open("a") as f:
        f.write(json.dumps({"t": time.time(), "event": kind, **data}) + "\n")


class Brain:
    """Bridge between audio and agent"""

    def __init__(
        self,
        llm: Backend | None = None,
        maker: async_sessionmaker[AsyncSession] = SessionLocal,
    ) -> None:
        self.llm = llm or build_llm()
        self.maker = maker
        self.conv = Conversation()

    async def reply(self, text: str) -> str:
        was_active = self.conv.status == "active"
        async with self.maker() as s:
            out = await agent.run_turn(self.conv, text, s, self.llm, date.today())
        if was_active and self.conv.status != "active":
            log_event("handoff", conversation_id=self.conv.id, status=self.conv.status)
        return out
