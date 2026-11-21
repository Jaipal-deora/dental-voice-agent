from collections.abc import AsyncIterator
from datetime import datetime, time, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from dental_agent.db import get_session
from dental_agent.db_models import Base, OpeningHours, Slot
from dental_agent.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # test only
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        t = datetime(2030, 1, 7, 9)
        s.add_all(
            Slot(
                starts_at=t + timedelta(minutes=30 * i),
                ends_at=t + timedelta(minutes=30 * i + 30),
            )
            for i in range(4)
        )
        s.add(OpeningHours(weekday=0, opens=time(9), closes=time(17)))
        await s.commit()

    async def override() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()
