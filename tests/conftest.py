from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db.session import get_session
from app.main import app


@pytest.fixture(name="session")
def session_fixture() -> Iterator[Session]:
    """An empty in-memory database, rebuilt for every test.

    StaticPool forces every connection to reuse the same in-memory database;
    without it SQLite hands out a fresh empty one per connection and the tables
    created here vanish before the request sees them.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Iterator[TestClient]:
    """A client whose requests run against the throwaway database.

    dependency_overrides swaps get_session for one returning the test session.
    This is the payoff for injecting the session in commit 25: no route needs to
    know it is being tested.
    """

    def session_override() -> Session:
        return session

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
