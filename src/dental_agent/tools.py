import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from dental_agent import service
from dental_agent.conversation import Conversation, PendingAction
from dental_agent.messages import msg
from dental_agent.tracing import tracer

Result = dict[str, Any]


@dataclass
class Ctx:
    session: AsyncSession
    conv: Conversation


class SearchArgs(BaseModel):
    date: str | None = Field(None, description="ISO date, e.g. 1900-01-01")
    daypart: Literal["morning", "afternoon", "evening"] | None = None


class NoArgs(BaseModel):
    pass


class FindArgs(BaseModel):
    phone: str


class BookArgs(BaseModel):
    patient_name: str
    phone: str
    slot_id: int


class RescheduleArgs(BaseModel):
    appointment_id: int
    new_slot_id: int


class CancelArgs(BaseModel):
    appointment_id: int


class ConfirmArgs(BaseModel):
    confirmed: bool


class HandoffArgs(BaseModel):
    reason: str


def _part(t: datetime) -> str:
    return "morning" if t.hour < 12 else "afternoon" if t.hour < 17 else "evening"


async def _search(c: Ctx, a: SearchArgs) -> Result:
    rows = await service.list_slots(c.session, limit=200)
    hits = [
        r
        for r in rows
        if (not a.date or r.starts_at.date().isoformat() == a.date)
        and (not a.daypart or _part(r.starts_at) == a.daypart)
    ]
    return {
        "slots": [
            {"slot_id": r.id, "starts_at": r.starts_at.isoformat(timespec="minutes")}
            for r in hits[:8]
        ]
    }


async def _hours(c: Ctx, a: NoArgs) -> Result:
    rows = await service.get_hours(c.session)
    return {
        "hours": [
            {"weekday": r.weekday, "opens": str(r.opens), "closes": str(r.closes)}
            for r in rows
        ]
    }


async def _find(c: Ctx, a: FindArgs) -> Result:
    rows = await service.appointments_for_phone(c.session, a.phone)
    return {
        "appointments": [
            {
                "appointment_id": ap.id,
                "starts_at": sl.starts_at.isoformat(timespec="minutes"),
            }
            for ap, sl in rows
        ]
    }


async def _book(c: Ctx, a: BookArgs) -> Result:
    key = hashlib.sha256(f"{c.conv.id}:{a.slot_id}:{a.phone}".encode()).hexdigest()[:32]
    try:
        appt = await service.book(c.session, a.patient_name, a.phone, a.slot_id, key)
    except (service.NotFound, service.SlotTaken) as e:
        return {"error": type(e).__name__}
    c.conv.events.append("booked")
    return {"appointment_id": appt.id, "slot_id": appt.slot_id}


async def _reschedule(c: Ctx, a: RescheduleArgs) -> Result:
    try:
        appt = await service.reschedule(c.session, a.appointment_id, a.new_slot_id)
    except (service.NotFound, service.SlotTaken) as e:
        return {"error": type(e).__name__}
    c.conv.events.append("booked")
    return {"appointment_id": appt.id, "slot_id": appt.slot_id}


async def _cancel(c: Ctx, a: CancelArgs) -> Result:
    try:
        await service.cancel(c.session, a.appointment_id)
    except service.NotFound as e:
        return {"error": type(e).__name__}
    c.conv.events.append("cancelled")
    return {"status": "cancelled"}


async def _handoff(c: Ctx, a: HandoffArgs) -> Result:
    c.conv.status = "escalated"
    c.conv.events.append("escalated")
    c.conv.final_text = msg("handoff")
    return {"status": "handed_off", "reason": a.reason}


async def _confirm(c: Ctx, a: ConfirmArgs) -> Result:
    p = c.conv.pending
    if p is None:
        return {"error": "nothing is pending"}
    if c.conv.user_turns <= p.proposed_turn:
        return {"error": "the caller has not replied yet; ask them first"}
    c.conv.pending = None
    if not a.confirmed:
        return {"status": "caller declined; nothing changed"}
    tool = REGISTRY[p.tool]
    return await tool.handler(c, tool.args.model_validate(p.args))


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    handler: Callable[[Ctx, Any], Awaitable[Result]]
    needs_confirm: bool = False


TOOLSET = [
    Tool(
        "search_slots",
        "List open slots; filter by date and daypart.",
        SearchArgs,
        _search,
    ),
    Tool("get_hours", "Opening hours by weekday (0 is Monday).", NoArgs, _hours),
    Tool(
        "find_appointments",
        "Find a caller's booked appointments by phone.",
        FindArgs,
        _find,
    ),
    Tool("book", "Book a slot. Needs caller confirmation.", BookArgs, _book, True),
    Tool(
        "reschedule",
        "Move an appointment. Needs caller confirmation.",
        RescheduleArgs,
        _reschedule,
        True,
    ),
    Tool(
        "cancel",
        "Cancel an appointment. Needs caller confirmation.",
        CancelArgs,
        _cancel,
        True,
    ),
    Tool(
        "confirm_pending",
        "Call only after the caller has answered yes or no to your "
        "confirmation question.",
        ConfirmArgs,
        _confirm,
    ),
    Tool(
        "handoff_to_human",
        "Transfer to staff when the caller asks for a person.",
        HandoffArgs,
        _handoff,
    ),
]

REGISTRY = {t.name: t for t in TOOLSET}
TOOLS = [
    {
        "name": t.name,
        "description": t.description,
        "input_schema": t.args.model_json_schema(),
    }
    for t in TOOLSET
]


async def execute(name: str, raw: dict[str, Any], c: Ctx) -> Result:
    tool = REGISTRY.get(name)
    if tool is None:
        return {"error": f"unknown tool {name}"}

    try:
        args = tool.args.model_validate(raw)
    except ValidationError as e:
        return {"error": "invalid arguments", "detail": str(e)[:300]}
    with tracer.start_as_current_span(f"tool:{name}") as span:
        span.set_attribute("input.value", json.dumps(raw))
        if tool.needs_confirm:
            c.conv.pending = PendingAction(
                name, args.model_dump(), c.conv.user_turns
            )
            out: Result = {
                "status": "needs_confirmation",
                "action": name,
                "details": args.model_dump(),
                "instruction": "Read the details back and ask the caller for a clear yes or no. "
                "Do not call confirm_pending until they reply.",
            }
        else:
            out = await tool.handler(c, args)
        span.set_attribute("output.value", json.dumps(out, default=str))
    return out
