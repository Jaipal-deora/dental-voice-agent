import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from dental_agent.db import SessionLocal
from dental_agent.db_models import OpeningHours, Patient, Slot
from dental_agent.seed import seed


@pytest.mark.manual 
def test_seed_database():
    asyncio.run(_test_seed_database())

async def _test_seed_database():
    async with SessionLocal() as s:
        await s.execute(Slot.__table__.delete())
        await s.execute(Patient.__table__.delete())
        await s.execute(OpeningHours.__table__.delete())
        await s.commit()

    await seed()

    async with SessionLocal() as s:
        # test patients
        patients = await s.scalar(select(func.count()).select_from(Patient))

        assert patients == 1 

        patient = (
            await s.execute(select(Patient))
        ).scalars().first()

        assert patient.name == "foo"
        assert patient.phone == "03001234567"

        # test opening hours 
        hours = await s.scalar(select(func.count()).select_from(OpeningHours))

        assert hours == 6

        opening_hours = (await s.execute(select(OpeningHours))).scalars().all()

        for hour in opening_hours:
            assert hour.opens.hour == 9 
            assert hour.closes.hour == 17

        weekdays = {hour.weekday for hour in opening_hours}
        assert weekdays == {i for i in range(6)}

        # test slots 
        slots = (await s.execute(select(Slot))).scalars().all()

        today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)

        working_days = sum(1 for n in range(1,15) if (today + timedelta(days=n)).weekday() != 6)

        expected_slots = working_days * 16 

        assert expected_slots == len(slots)

        # verify appointment durations 
        for slot in slots:
            duration = slot.ends_at - slot.starts_at

            assert duration == timedelta(minutes=30)

            assert slot.starts_at.weekday() != 6 
        print('All seed database tests passed!')
