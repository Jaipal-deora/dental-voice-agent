from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dental_agent.db_models import Appointment, OpeningHours, Patient, Slot


class NotFound(Exception):
    pass 

class SlotTaken(Exception):
    pass 

async def list_slots(s: AsyncSession, limit: int = 50) -> list[Slot]:
    booked = select(Appointment.slot_id).where(Appointment.status=="booked")
    q = select(Slot).where(Slot.id.not_in(booked)).order_by(Slot.starts_at).limit(limit)
    return list((await s.scalars(q)).all())

async def get_hours(s:AsyncSession) -> list[OpeningHours]:
    hours = select(OpeningHours).order_by(OpeningHours.weekday)
    return list((await s.scalars(hours)).all()) 

async def _by_key(s:AsyncSession, key:str) -> Appointment | None:
    return await s.scalar(select(Appointment).where(Appointment.idempotency_key==key))

async def book(s:AsyncSession, name:str, phone:str, slot_id: int, key:str) -> Appointment:
    if existing := await _by_key(s,key):
        return existing 

    if await s.get(Slot,slot_id) is None:
        raise NotFound("slot")

    patient = await s.scalar(select(Patient).where(Patient.phone == phone))
    if patient is None:
        patient = Patient(name=name,phone=phone)
        s.add(patient)
        await s.flush()

    appt = Appointment(patient_id=patient.id,slot_id=slot_id,idempotency_key=key)
    s.add(appt)

    try:
        await s.commit()
    except IntegrityError:
        await s.rollback()

        if existing := await _by_key(s,key):
            return existing
        raise SlotTaken from None
    return appt 


async def reschedule(s:AsyncSession, appt_id: int, new_slot_id: int) -> Appointment:
    appt = await s.get(Appointment, appt_id)

    if appt is None or appt.status != 'booked':
        raise NotFound("appointment")

    if appt.slot_id == new_slot_id:
        return appt

    if await s.get(Slot,new_slot_id) is None:
        raise NotFound('slot')

    appt.slot_id = new_slot_id
    try:
        await s.commit()

    except IntegrityError:
        await s.rollback()
        raise SlotTaken from None
    return appt 
        

async def cancel(s: AsyncSession, appt_id:int) -> Appointment:
    appt = await s.get(Appointment,appt_id)

    if appt is None:
        raise NotFound("appointment")

    appt.status = "cancelleld"
    await s.commit()
    return appt 

