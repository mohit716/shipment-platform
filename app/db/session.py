from sqlmodel import create_engine

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
