import pytest
from sqlmodel import select

from app.models.user import User
from app.seed import CUSTOMER_EMAIL, STAFF_EMAIL, seed

pytestmark = pytest.mark.anyio


async def test_seed_creates_the_demo_accounts(session_factory, monkeypatch) -> None:
    monkeypatch.setattr("app.seed.AsyncSessionLocal", session_factory)

    await seed()

    async with session_factory() as session:
        emails = {
            user.email
            for user in (await session.exec(select(User))).all()
        }
    assert emails == {CUSTOMER_EMAIL, STAFF_EMAIL}


async def test_seed_is_safe_to_run_twice(session_factory, monkeypatch) -> None:
    monkeypatch.setattr("app.seed.AsyncSessionLocal", session_factory)

    await seed()
    await seed()

    async with session_factory() as session:
        users = list((await session.exec(select(User))).all())
    # A second run that inserted again would violate the unique email
    # constraint and raise; two accounts after two runs is the success case.
    assert len(users) == 2
