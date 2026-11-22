from typing import Any

from dental_agent.backends import ModelReply, ToolCall


class ScriptedLLM:
    def __init__(self, replies: list[ModelReply]) -> None:
        self.replies = list(replies)

    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelReply:
        return self.replies.pop(0)


class LoopingLLM:
    def __init__(self, reply: ModelReply) -> None:
        self.reply = reply

    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelReply:
        return self.reply


def text(t: str, tokens: int = 10) -> ModelReply:
    return ModelReply(t, [], [{"type": "text", "text": t}], tokens)


def call(name: str, tokens: int = 10, **args: Any) -> ModelReply:
    tc = ToolCall(f"tu_{name}", name, args)
    return ModelReply(
        "",
        [tc],
        [{"type": "tool_use", "id": tc.id, "name": name, "input": args}],
        tokens,
    )
