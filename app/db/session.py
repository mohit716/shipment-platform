from collections.abc import AsyncIterator, Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import Session, SQLModel, create_engine

# SQLite keeps the first database commits dependency free: the whole database is
# one file next to the code. PostgreSQL replaces this in phase 5, and the only
# line that has to change is the URL.
DATABASE_URL = "sqlite:///./fleetline.db"
ASYNC_DATABASE_URL = "sqlite+aiosqlite:///./fleetline.db"

# check_same_thread is a SQLite-only guard that forbids using one connection from
# more than one thread. FastAPI serves requests from a thread pool, so it has to
# be lifted; every other database driver ignores this argument entirely.
engine = create_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False},
)

# The async engine speaks to the same file through aiosqlite. Both engines exist
# for exactly one commit: the routes move across in the next one, and the
# synchronous engine is deleted there.
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False},
)

# expire_on_commit=False is close to mandatory in async code. The default expires
# every attribute after commit, so the next attribute read triggers a lazy reload,
# and a lazy reload inside async code raises MissingGreenlet.
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def create_db_and_tables() -> None:
    """Create any table that does not yet exist.

    This reads SQLModel.metadata, which is only populated for model classes that
    have actually been imported, hence the import below. It creates missing
    tables but never alters an existing one, so a changed column is silently
    ignored. Alembic takes this over in phase 5.
    """
    from app.models import shipment  # noqa: F401  (registers the table)

    SQLModel.metadata.create_all(engine)


async def create_db_and_tables_async() -> None:
    """Async equivalent of create_db_and_tables.

    metadata.create_all is synchronous SQLAlchemy code, so it cannot simply be
    awaited. run_sync hands it a synchronous connection driven by the async one.
    """
    from app.models import shipment  # noqa: F401  (registers the table)

    async with async_engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)


def get_session() -> Iterator[Session]:
    """Yield a session for one request, then close it.

    A dependency that yields runs its teardown after the response is produced,
    so the session is guaranteed to close even when the handler raises. Tests
    override this to point at a throwaway database.
    """
    with Session(engine) as session:
        yield session


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Yield an async session for one request, then close it."""
    async with AsyncSessionLocal() as session:
        yield session


# Aliases so handlers read as `session: SessionDep` rather than repeating the
# Annotated/Depends pair on every route.
SessionDep = Annotated[Session, Depends(get_session)]
AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
