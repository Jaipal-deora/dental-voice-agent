import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, Protocol, cast

from openai import (
    APIConnectionError,
    APIError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

from dental_agent.config import settings
from dental_agent.groq_client import client, reasoning_args
from dental_agent.messages import msg
from dental_agent.reliability import call_with_retries

log = logging.getLogger(__name__)

RETRYABLE = (
    TimeoutError,
    APIConnectionError,
    RateLimitError,
    InternalServerError,
    BadRequestError,
)


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ModelReply:
    text: str
    tool_calls: list[ToolCall]
    content: list[dict[str, Any]]  # the stored format: text and tool_use block
    tokens: int = 0
    degraded: bool = False


class Backend(Protocol):
    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelReply: ...


def _to_openai(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in messages:
        c = m["content"]
        if isinstance(c, str):
            out.append({"role": m["role"], "content": c})
        elif m["role"] == "assistant":
            text = "".join(b["text"] for b in c if b["type"] == "text")
            calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {
                        "name": b["name"],
                        "arguments": json.dumps(b["input"]),
                    },
                }
                for b in c
                if b["type"] == "tool_use"
            ]
            reply: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                reply["tool_calls"] = calls
            out.append(reply)
        else:  # a user turn that carries tool result becomes one tool message each
            for b in c:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": b["tool_use_id"],
                        "content": b["content"],
                    }
                )
    return out


def _tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


class GroqBackend:
    def __init__(self, model: str, max_tokens: int | None = None) -> None:
        self.model = model
        self.max_tokens = max_tokens or settings.max_output_tokens

    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelReply:
        extra: dict[str, Any] = reasoning_args(self.model)
        if tools:
            extra["tools"] = _tools(tools)
        r = await client.chat.completions.create(
            model=self.model,
            messages=cast(Any, _to_openai(system, messages)),
            max_completion_tokens=self.max_tokens,
            temperature=0,
            **extra,
        )

        choice = r.choices[0]

        if choice.finish_reason == "length":
            raise TimeoutError("output limit reached before the model finished")
        text = choice.message.content or ""
        content: list[dict[str, Any]] = [{"type": "text", "text": text}] if text else []
        calls: list[ToolCall] = []
        for tc in choice.message.tool_calls or []:
            if tc.type != "function":
                continue
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            calls.append(ToolCall(tc.id, tc.function.name, args))
            content.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": args,
                }
            )
        if not text and not calls:
            raise TimeoutError(
                "empty reply"
            )  # retried like any other transient failure
        return ModelReply(text, calls, content, r.usage.total_tokens if r.usage else 0)


class FallbackLLM:
    def __init__(self, backends: list[Backend]) -> None:
        self.backends = backends

    async def complete(
        self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelReply:
        for b in self.backends:
            try:
                return await call_with_retries(
                    partial(b.complete, system, messages, tools),
                    timeout=settings.agent_timeout_s,
                    attempts=settings.llm_max_attempts,
                    retry_on=RETRYABLE,
                )
            except (TimeoutError, APIError) as e:
                log.warning("backend %s failed: %r", type(b).__name__, e)
        text = msg("scripted")
        return ModelReply(text, [], [{"type": "text", "text": text}], degraded=True)


# def build_llm() -> FallbackLLM:
#     return FallbackLLM(
#         [GroqBackend(settings.agent_model), GroqBackend(settings.fallback_model)]
#     )


def build_llm(wrap: Callable[[Backend], Backend] = lambda b: b) -> FallbackLLM:
    models = [settings.agent_model, settings.fallback_model]
    return FallbackLLM([wrap(GroqBackend(m)) for m in models])
