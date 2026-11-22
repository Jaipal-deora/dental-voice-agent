from datetime import datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from dental_agent.db_models import Appointment, Base, OpeningHours, Patient, Slot


async def make_memory_maker(
    days: int = 1, per_day: int = 4, preload: bool = False
) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # test and eval only
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        t0 = datetime(2030, 1, 7, 9)
        s.add_all(
            Slot(
                starts_at=t0 + timedelta(days=d, minutes=30 * i),
                ends_at=t0 + timedelta(days=d, minutes=30 * i + 30),
            )
            for d in range(days)
            for i in range(per_day)
        )

        s.add_all(
            OpeningHours(weekday=d, opens=time(9), closes=time(17)) for d in range(5)
        )
        s.add(Patient(name="foo", phone="0300-0000001"))
        await s.flush()
        if preload:
            s.add(Appointment(patient_id=1, slot_id=1, idempotency_key="preload-0001"))
        await s.commit()
    return maker
