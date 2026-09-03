import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.main import app


@pytest.fixture(name="client")
def client_fixture(tmp_path: Path) -> Iterator[TestClient]:
    """A client backed by a throwaway database, rebuilt for every test.

    A file under tmp_path rather than an in-memory database: the app runs on its
    own event loop under TestClient, and an in-memory SQLite connection cannot be
    shared across loops. A file can be opened by whichever loop needs it.
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

    async def create_tables() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

    asyncio.run(create_tables())

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    # dependency_overrides swaps get_session for one pointing at the throwaway
    # database. This is the payoff for injecting the session in commit 25: no
    # route needs to know it is being tested.
    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
