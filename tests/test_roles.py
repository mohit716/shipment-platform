import pytest
from httpx import AsyncClient

from tests.conftest import promote_to_staff

pytestmark = pytest.mark.anyio


async def test_registration_creates_a_customer(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/auth/me")).json()["role"] == "customer"


async def test_registration_cannot_request_a_role(client: AsyncClient) -> None:
    # A role the client picks is not a permission boundary. UserCreate has no
    # role field, so asking for one is rejected outright.
    response = await client.post(
        "/users",
        json={
            "email": "sneaky@example.com",
            "full_name": "Sneaky Person",
            "password": "correct-horse",
            "role": "staff",
        },
    )
    assert response.status_code == 422


async def test_promotion_is_visible_on_the_next_request(
    auth_client: AsyncClient, session_factory
) -> None:
    await promote_to_staff(session_factory, "ada@example.com")
    # The role is read from the row on every request rather than baked into the
    # token, so a promotion takes effect immediately instead of when the
    # existing token happens to expire.
    assert (await auth_client.get("/auth/me")).json()["role"] == "staff"
