from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from dental_agent import service
from dental_agent.db import get_session
from dental_agent.db_models import Appointment, OpeningHours, Slot
from dental_agent.schemas import (
    AppointmentOut,
    BookRequest,
    HoursOut,
    RescheduleRequest,
    SlotOut,
)

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_session)]

def _http(e: Exception) -> HTTPException:
    if isinstance(e,service.NotFound):
        return HTTPException(404,f"{e} not found")
    return HTTPException(409,"slot already taken")

@router.get("/slots",response_model=list[SlotOut])
async def slots(db: Db) -> list[Slot]:
    return await service.list_slots(db)

@router.get("/hours",response_model=list[HoursOut])
async def hours(db:Db) -> list[OpeningHours]:
    return await service.get_hours(db)

@router.post("/appointments", response_model=AppointmentOut, status_code=201)
async def book(body:BookRequest, db:Db) -> Appointment:
    try:
        return await service.book(db,body.patient_name,body.phone,body.slot_id,body.idempotency_key)
    except (service.NotFound, service.SlotTaken) as e:
        raise _http(e) from e 

@router.put("/appointments/{appt_id}",response_model=AppointmentOut)
async def reschedule(appt_id:int, body:RescheduleRequest, db:Db) -> Appointment:
    try:
        return await service.reschedule(db,appt_id,body.new_slot_id)
    except (service.NotFound, service.SlotTaken) as e:
        raise _http(e) from e 

@router.delete("/appointments/{appt_id}",response_model=AppointmentOut)
async def cancel(appt_id: int, db:Db) -> Appointment:
    try:
        return await service.cancel(db,appt_id)
    except service.NotFound as e:
        raise _http(e) from e 



