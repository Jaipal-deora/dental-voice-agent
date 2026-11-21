import asyncio
from datetime import datetime, time, timedelta

from sqlalchemy import select

from dental_agent.db import SessionLocal
from dental_agent.db_models import OpeningHours, Patient, Slot


async def seed() -> None:
    async with SessionLocal() as s:
        if (await s.execute(select(OpeningHours))).first():
            return

        s.add_all(
            OpeningHours(weekday=d, opens=time(9), closes=time(17)) for d in range(6)
        )
        s.add(Patient(name="foo", phone="03001234567"))
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for n in range(1, 15):
            day = today + timedelta(days=n)
            if day.weekday() == 6:  # skip sunday
                continue
            for i in range(16):
                t = day + timedelta(hours=9, minutes=30 * i)
                s.add(Slot(starts_at=t, ends_at=t + timedelta(minutes=30)))
        await s.commit()


if __name__ == "__main__":
    asyncio.run(seed())
