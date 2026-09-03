from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio only.

    anyio would otherwise parameterise every test across asyncio and trio,
    doubling the suite for no benefit here.
    """
    return "asyncio"


@pytest.fixture(name="client")
async def client_fixture(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    """A client backed by a throwaway database, rebuilt for every test.

    A file under tmp_path rather than an in-memory database: an in-memory SQLite
    connection belongs to whichever connection created it, and sharing one
    between the test and the application is more trouble than a temporary file.
    """
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_async_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    # dependency_overrides swaps get_session for one pointing at the throwaway
    # database. This is the payoff for injecting the session in commit 25: no
    # route needs to know it is being tested.
    app.dependency_overrides[get_session] = session_override

    # ASGITransport calls the application in-process. There is no socket, no
    # port and no server, so the suite stays fast and needs nothing running.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()
