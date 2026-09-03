from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.main import app


@pytest.fixture(autouse=True, scope="session")
def _cheap_password_hashing() -> None:
    """Hash at bcrypt's minimum cost for the whole suite.

    Production wants the work factor high enough to make offline cracking
    expensive. A test suite that registers hundreds of throwaway accounts pays
    that cost hundreds of times for no security benefit; at the default this
    suite spent about three minutes hashing.
    """
    settings.bcrypt_rounds = 4


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


@pytest.fixture(name="customer")
async def customer_fixture(client: AsyncClient) -> dict:
    """A registered account, returned as the API represents it."""
    response = await client.post(
        "/users",
        json={
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "password": "correct-horse",
        },
    )
    return response.json()


@pytest.fixture(name="auth_client")
async def auth_client_fixture(client: AsyncClient, customer: dict) -> AsyncClient:
    """The same client, logged in as the customer fixture.

    Setting the header once here rather than per request keeps the tests about
    the behaviour under test instead of about authentication plumbing.
    """
    response = await client.post(
        "/auth/token",
        data={"username": "ada@example.com", "password": "correct-horse"},
    )
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


async def login_as(client: AsyncClient, email: str, full_name: str) -> dict[str, str]:
    """Register a second account and return its Authorization header.

    Used by the ownership tests, which need two callers to prove one cannot see
    the other's shipments.
    """
    await client.post(
        "/users",
        json={"email": email, "full_name": full_name, "password": "correct-horse"},
    )
    response = await client.post(
        "/auth/token", data={"username": email, "password": "correct-horse"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
