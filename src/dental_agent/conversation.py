import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass 
class PendingAction:
    tool:str 
    args: dict[str, Any]
    proposed_turn: int 

@dataclass 
class Conversation:
    id:str= field(default_factory=lambda: uuid.uuid4().hex)
    messages: list[dict[str,Any]] = field(default_factory=list)
    status:str = "active" # active | escalated | closed
    user_turns: int = 0 
    tool_calls_used:int = 0
    tokens_used:int = 0
    pending: PendingAction | None = None 
    events: list[str] = field(default_factory=list)
    final_text:str = ""

    def outcome(self) -> str:
        if self.status != "active":
            return "escalated"
        for e in reversed(self.events):
            if e in ("booked", "cancelled"):
                return e 
        return "refused"

class InMemoryStore:
    def __init__(self) -> None:
        self._d:dict[str, Conversation] = {}

    def get(self,cid:str|None) -> Conversation:
        if cid and cid in self._d:
            return self._d[cid]
        c = Conversation()
        self._d[c.id] = c
        return c 
