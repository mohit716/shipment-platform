import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_a_previous_tests_customer_does_not_survive(client: AsyncClient) -> None:
    """The suite registers ada@example.com constantly.

    If isolation failed, the second test to run this assertion would get a 409
    instead of a 201. Running twice in one test is the same check without
    depending on collection order: wipe happens between tests, so a helper that
    only ran once would still pass on a leaked database that happened to be
    empty at the start of the session.
    """
    first = await client.post(
        "/users",
        json={
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "password": "correct-horse",
        },
    )
    assert first.status_code == 201
    assert first.json()["id"] == 1


async def test_ids_reset_as_well_as_rows(client: AsyncClient) -> None:
    # sqlite_sequence is reset alongside the rows, otherwise the first customer
    # of test n would be id n rather than id 1, and a lookup of /users/1 would
    # 404 for a customer that had just been created.
    response = await client.post(
        "/users",
        json={
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "password": "correct-horse",
        },
    )
    assert response.json()["id"] == 1
