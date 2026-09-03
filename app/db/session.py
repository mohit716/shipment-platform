from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

# SQLModel's AsyncSession, not SQLAlchemy's. They are otherwise identical, but
# only this one keeps .exec(), which returns typed rows for a select(Model).
from sqlmodel.ext.asyncio.session import AsyncSession

# SQLite keeps the first database commits dependency free: the whole database is
# one file next to the code. PostgreSQL replaces this in phase 5, and the only
# line that has to change is the URL. aiosqlite is the driver that lets the
# async engine talk to it without blocking the event loop.
DATABASE_URL = "sqlite+aiosqlite:///./fleetline.db"

# check_same_thread is a SQLite-only guard that forbids using one connection from
# more than one thread; every other database driver ignores this argument.
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False},
)

# expire_on_commit=False is close to mandatory in async code. The default expires
# every attribute after commit, so the next attribute read triggers a lazy reload,
# and a lazy reload inside async code raises MissingGreenlet.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db_and_tables() -> None:
    """Create any table that does not yet exist.

    metadata.create_all is synchronous SQLAlchemy code, so it cannot simply be
    awaited; run_sync hands it a synchronous connection driven by the async one.
    It also reads SQLModel.metadata, which is only populated for models that have
    actually been imported, hence the import below. Tables that already exist are
    never altered, which is why Alembic arrives in phase 5.
    """
    from app.models import shipment  # noqa: F401  (registers the table)

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a session for one request, then close it.

    A dependency that yields runs its teardown after the response is produced,
    so the session is guaranteed to close even when the handler raises. Tests
    override this to point at a throwaway database.
    """
    async with AsyncSessionLocal() as session:
        yield session


# Alias so handlers read as `session: SessionDep` rather than repeating the
# Annotated/Depends pair on every route.
SessionDep = Annotated[AsyncSession, Depends(get_session)]
