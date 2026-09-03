from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlmodel import select

from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.schemas.user import UserRole


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


@pytest.fixture(name="session_factory")
async def session_factory_fixture(tmp_path: Path) -> AsyncIterator[object]:
    """A throwaway database, rebuilt for every test.

    A file under tmp_path rather than an in-memory database: an in-memory SQLite
    connection belongs to whichever connection created it, and sharing one
    between the test and the application is more trouble than a temporary file.

    Exposed as its own fixture so a test can reach the database directly, which
    is how staff promotion is done: there is no endpoint for it.
    """
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_async_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    yield factory

    await engine.dispose()


@pytest.fixture(name="client")
async def client_fixture(session_factory) -> AsyncIterator[AsyncClient]:
    """An HTTP client wired to the throwaway database."""

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


async def promote_to_staff(session_factory, email: str) -> None:
    """Flip an account to staff by writing to the database directly.

    There is no endpoint for this on purpose. Promotion is an operational act,
    not an API feature, so the test reaches past the API the same way an
    administrator would.
    """
    async with session_factory() as session:
        result = await session.exec(select(User).where(User.email == email))
        user = result.one()
        user.role = UserRole.staff
        session.add(user)
        await session.commit()


@pytest.fixture(name="staff_client")
async def staff_client_fixture(
    auth_client: AsyncClient, session_factory
) -> AsyncClient:
    """The logged-in client, promoted to staff.

    The role is read from the row on every request, so the token minted before
    the promotion keeps working and immediately carries the new permissions.
    """
    await promote_to_staff(session_factory, "ada@example.com")
    return auth_client


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
