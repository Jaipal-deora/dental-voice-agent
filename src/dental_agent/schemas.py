from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    starts_at: datetime
    ends_at: datetime


class HoursOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    weekday: int
    opens: time
    closes: time


class BookRequest(BaseModel):
    patient_name: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=11, max_length=13)
    slot_id: int
    idempotency_key: str = Field(min_length=8, max_length=64)


class RescheduleRequest(BaseModel):
    new_slot_id: int


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slot_id: int
    status: str


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class BookingIntent(BaseModel):
    intent: Literal["book", "reschedule", "cancel", "hours", "unknown"]
    day: str | None = None
    daypart: Literal["morning", "afternoon", "evening"] | None = None
    service: str | None = None
    confidence: float = Field(ge=0, le=1)
