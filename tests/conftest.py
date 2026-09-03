from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.ratelimit import login_limiter
from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.schemas.user import UserRole
from app.services.notifications import MemoryNotifier, get_notifier
from tests.factories import bearer, login, register


@pytest.fixture(autouse=True, scope="session")
def _cheap_password_hashing() -> None:
    """Hash at bcrypt's minimum cost for the whole suite.

    Production wants the work factor high enough to make offline cracking
    expensive. A test suite that registers hundreds of throwaway accounts pays
    that cost hundreds of times for no security benefit; at the default this
    suite spent about three minutes hashing.
    """
    settings.bcrypt_rounds = 4


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Run async tests on asyncio only.

    anyio would otherwise parameterise every test across asyncio and trio,
    doubling the suite for no benefit here.

    Session scoped because the engine fixture is: an async fixture cannot
    depend on a narrower-scoped one, and pytest reports that as a ScopeMismatch
    rather than anything about event loops.
    """
    return "asyncio"


@pytest.fixture(name="engine", scope="session")
async def engine_fixture(
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[AsyncEngine]:
    """One database for the whole run, with the schema built once.

    Previously every test created its own file and ran create_all. That is
    perfectly isolated and pays for the schema hundreds of times; isolation is
    now a table wipe after each test instead, which is far cheaper.

    A file rather than an in-memory database: an in-memory SQLite database
    belongs to the connection that created it, and this fixture deliberately
    hands out several connections. StaticPool keeps them all on one connection
    so they see the same file state.
    """
    path = tmp_path_factory.mktemp("fleetline") / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False},
        # One connection for the whole session, so every session in a test sees
        # the same uncommitted transaction.
        poolclass=StaticPool,
    )

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(name="session_factory")
async def session_factory_fixture(engine: AsyncEngine) -> AsyncIterator[object]:
    """Sessions against the shared schema, emptied after each test.

    Nested-transaction rollback is the usual trick, but SQLite plus aiosqlite
    does not honour SAVEPOINT the way PostgreSQL does: a commit inside the
    application still leaked rows into the next test. Deleting every row and
    resetting sqlite_sequence is slower than a rollback and far more honest
    about what isolation actually requires here.

    Exposed as its own fixture so a test can reach the database directly, which
    is how staff promotion is done: there is no endpoint for it.
    """
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield factory

    async with factory() as session:
        # Children first, otherwise a foreign key from packages to shipments
        # would refuse the delete. sorted_tables is already topological.
        for table in reversed(SQLModel.metadata.sorted_tables):
            await session.execute(delete(table))
        # Without this, ids keep climbing and a test that happens to look up
        # /users/1 after fifty others would miss the customer it just created.
        sequences = await session.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='sqlite_sequence'"
            )
        )
        if sequences.first() is not None:
            await session.execute(text("DELETE FROM sqlite_sequence"))
        await session.commit()


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    """Empty the rate limiter between tests.

    It is process-global state, so without this the tests interfere with each
    other in whatever order they happen to run, and the failure looks like a
    flaky test rather than shared state.
    """
    login_limiter.reset()


@pytest.fixture(name="outbox")
def outbox_fixture() -> MemoryNotifier:
    """Collects every notification the application tries to send."""
    return MemoryNotifier()


@pytest.fixture(name="client")
async def client_fixture(
    session_factory, outbox: MemoryNotifier
) -> AsyncIterator[AsyncClient]:
    """An HTTP client wired to the throwaway database and a recording notifier."""

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    # dependency_overrides swaps get_session for one pointing at the throwaway
    # database. This is the payoff for injecting the session in commit 25: no
    # route needs to know it is being tested.
    app.dependency_overrides[get_session] = session_override
    # Same trick as the session: the routes are unaware they are being tested.
    app.dependency_overrides[get_notifier] = lambda: outbox

    # ASGITransport calls the application in-process. There is no socket, no
    # port and no server, so the suite stays fast and needs nothing running.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(name="customer")
async def customer_fixture(client: AsyncClient) -> dict:
    """A registered account, returned as the API represents it."""
    return await register(client)


@pytest.fixture(name="auth_client")
async def auth_client_fixture(client: AsyncClient, customer: dict) -> AsyncClient:
    """The same client, logged in as the customer fixture.

    Setting the header once here rather than per request keeps the tests about
    the behaviour under test instead of about authentication plumbing.
    """
    token = await login(client, email=customer["email"])
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
    return await bearer(client, email=email, full_name=full_name)
