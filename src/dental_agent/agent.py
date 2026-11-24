import json
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from dental_agent.backends import Backend
from dental_agent.config import settings
from dental_agent.conversation import Conversation
from dental_agent.messages import msg
from dental_agent.tools import TOOLS, Ctx, execute
from dental_agent.tracing import tracer

SYSTEM_OLD = (
    "You are the phone receptionist of a small dental clinic. Today is {today}. "
    "Reply in {language}, in one or two short sentences. You can book, reschedule and cancel "
    "appointments, give opening hours, and hand over to a person. Collect name and phone before "
    "booking. Never invent slots; use search_slots. For book, reschedule and cancel the system "
    "asks you to confirm: read the details back, wait for the caller's yes or no, then call "
    "confirm_pending. Politely decline medical advice and anything unrelated to the clinic. "
    "If the caller asks for a person, call handoff_to_human."
)

SYSTEM = (
    "You are the phone receptionist of a small dental clinic. Today is {today}. "
    "Reply in {language}, in one or two short sentences. You can book, reschedule and cancel "
    "appointments, give opening hours, and hand over to a person. Collect name and phone before "
    "booking. Never invent slots; use search_slots. For book, reschedule and cancel the system "
    "asks you to confirm: read the details back in plain words, wait for the caller's yes or no, "
    "then call confirm_pending. Politely decline medical advice and anything unrelated to the "
    "clinic. If the caller asks for a person, call handoff_to_human. "
    "Speak like a person on the phone. Never say internal ids, slot numbers, appointment numbers "
    "or tool names. Refer to an appointment by weekday, date and time, for example "
    "'Tuesday 25 November at 11:00 am'."
)


def system_prompt(today: date) -> str:
    return SYSTEM.format(today=today.isoformat(), language=settings.agent_language)


def _close(conv: Conversation, text: str) -> str:
    conv.status = "closed"
    conv.final_text = text
    return text


async def run_turn(
    conv: Conversation, text: str, session: AsyncSession, llm: Backend, today: date
) -> str:
    if conv.status != "active":
        return msg("closed")
    conv.user_turns += 1
    conv.messages.append({"role": "user", "content": text})
    ctx = Ctx(session, conv)
    with tracer.start_as_current_span("agent.turn") as span:
        span.set_attribute("input.value", text)
        while True:
            if conv.tokens_used >= settings.max_conversation_tokens:
                return _close(conv, msg("limit"))
            reply = await llm.complete(system_prompt(today), conv.messages, TOOLS)
            conv.tokens_used += reply.tokens
            conv.messages.append({"role": "assistant", "content": reply.content})
            if reply.degraded:
                conv.status = "escalated"
                conv.events.append("escalated")
                conv.events.append(
                    "degraded"
                )  # added for evals to separate outages from wrong answers
                return reply.text
            if not reply.tool_calls:
                span.set_attribute("output.value", reply.text)
                return reply.text
            results: list[dict[str, Any]] = []
            for call in reply.tool_calls:
                if conv.tool_calls_used >= settings.max_tool_calls:
                    return _close(conv, msg("limit"))
                conv.tool_calls_used += 1
                out = await execute(call.name, call.input, ctx)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": json.dumps(out, default=str),
                    }
                )
            conv.messages.append({"role": "user", "content": results})
            if conv.status != "active":
                return conv.final_text
