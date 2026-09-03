import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

DEPOT = {"code": "LDS1", "name": "Leeds Central", "city": "Leeds"}


async def test_a_customer_cannot_register_a_depot(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/warehouses", json=DEPOT)
    assert response.status_code == 403


async def test_staff_can_register_a_depot(staff_client: AsyncClient) -> None:
    assert (await staff_client.post("/warehouses", json=DEPOT)).status_code == 201


async def test_a_customer_can_still_read_depots(
    staff_client: AsyncClient, auth_client: AsyncClient
) -> None:
    # Same underlying client, promoted; reading is deliberately not restricted
    # because a customer needs to see where their parcel has been.
    await staff_client.post("/warehouses", json=DEPOT)
    assert (await auth_client.get("/warehouses")).status_code == 200


async def test_a_customer_cannot_define_a_handling_label(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post("/tags", json={"name": "fragile"})
    assert response.status_code == 403


async def test_staff_can_define_a_handling_label(staff_client: AsyncClient) -> None:
    assert (
        await staff_client.post("/tags", json={"name": "fragile"})
    ).status_code == 201


async def test_a_customer_cannot_browse_the_customer_list(
    auth_client: AsyncClient,
) -> None:
    assert (await auth_client.get("/users")).status_code == 403


async def test_staff_can_browse_the_customer_list(staff_client: AsyncClient) -> None:
    assert (await staff_client.get("/users")).status_code == 200


async def test_an_anonymous_caller_gets_401_not_403(client: AsyncClient) -> None:
    # 401 means "who are you", 403 means "I know who you are and the answer is
    # no". The distinction tells a client whether logging in would help.
    assert (await client.post("/warehouses", json=DEPOT)).status_code == 401
