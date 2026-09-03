import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

VALID_USER = {"email": "ada@example.com", "full_name": "Ada Lovelace"}


async def test_registration_returns_the_created_customer(client: AsyncClient) -> None:
    response = await client.post("/users", json=VALID_USER)
    assert response.status_code == 201
    created = response.json()
    assert created["id"] >= 1
    assert created["email"] == VALID_USER["email"]


async def test_duplicate_email_is_rejected_with_409(client: AsyncClient) -> None:
    await client.post("/users", json=VALID_USER)
    response = await client.post("/users", json=VALID_USER)
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


async def test_malformed_email_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/users", json={**VALID_USER, "email": "not-an-email"}
    )
    assert response.status_code == 422


async def test_reading_a_missing_customer_returns_404(client: AsyncClient) -> None:
    assert (await client.get("/users/4242")).status_code == 404
