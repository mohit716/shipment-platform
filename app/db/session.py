from sqlmodel import SQLModel, create_engine

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
