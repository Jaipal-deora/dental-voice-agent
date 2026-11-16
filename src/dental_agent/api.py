from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from dental_agent import service
from dental_agent.db import get_session
from dental_agent.db_models import OpeningHours, Slot
from dental_agent.schemas import (
    HoursOut,
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


