from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine

# SQLite keeps the first database commits dependency free: the whole database is
# one file next to the code. PostgreSQL replaces this in phase 5, and the only
# line that has to change is the URL.
DATABASE_URL = "sqlite:///./fleetline.db"

# check_same_thread is a SQLite-only guard that forbids using one connection from
# more than one thread. FastAPI serves requests from a thread pool, so it has to
# be lifted; every other database driver ignores this argument entirely.
engine = create_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False},
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


def get_session() -> Iterator[Session]:
    """Yield a session for one request, then close it.

    A dependency that yields runs its teardown after the response is produced,
    so the session is guaranteed to close even when the handler raises. Tests
    override this to point at a throwaway database.
    """
    with Session(engine) as session:
        yield session


# Alias so handlers read as `session: SessionDep` rather than repeating the
# Annotated/Depends pair on every route.
SessionDep = Annotated[Session, Depends(get_session)]
