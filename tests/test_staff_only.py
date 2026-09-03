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


BOOKING = {"content": "ceramic dinnerware", "weight_kg": 2.4, "destination": 11001}


async def test_staff_see_every_customers_shipments(
    auth_client: AsyncClient, session_factory
) -> None:
    from tests.conftest import login_as, promote_to_staff

    mine = (await auth_client.post("/shipments", json=BOOKING)).json()
    other = await login_as(auth_client, "grace@example.com", "Grace Hopper")
    theirs = (
        await auth_client.post("/shipments", json=BOOKING, headers=other)
    ).json()

    await promote_to_staff(session_factory, "ada@example.com")
    rows = (await auth_client.get("/shipments")).json()

    assert {row["id"] for row in rows} == {mine["id"], theirs["id"]}


async def test_staff_can_narrow_the_list_to_one_customer(
    auth_client: AsyncClient, session_factory
) -> None:
    from tests.conftest import login_as, promote_to_staff

    await auth_client.post("/shipments", json=BOOKING)
    other = await login_as(auth_client, "grace@example.com", "Grace Hopper")
    theirs = (
        await auth_client.post("/shipments", json=BOOKING, headers=other)
    ).json()

    await promote_to_staff(session_factory, "ada@example.com")
    rows = (
        await auth_client.get(
            "/shipments", params={"customer_id": theirs["customer_id"]}
        )
    ).json()

    assert [row["id"] for row in rows] == [theirs["id"]]


async def test_a_customer_cannot_use_the_customer_id_filter(
    auth_client: AsyncClient,
) -> None:
    mine = (await auth_client.post("/shipments", json=BOOKING)).json()
    other = await login_as_other(auth_client)
    theirs = (
        await auth_client.post("/shipments", json=BOOKING, headers=other)
    ).json()

    # The parameter is accepted but ignored for customers: their own scope is
    # applied instead, so passing somebody else's id does not widen anything.
    rows = (
        await auth_client.get(
            "/shipments", params={"customer_id": theirs["customer_id"]}
        )
    ).json()
    assert [row["id"] for row in rows] == [mine["id"]]


async def login_as_other(client: AsyncClient) -> dict[str, str]:
    from tests.conftest import login_as

    return await login_as(client, "grace@example.com", "Grace Hopper")


async def test_an_anonymous_caller_gets_401_not_403(client: AsyncClient) -> None:
    # 401 means "who are you", 403 means "I know who you are and the answer is
    # no". The distinction tells a client whether logging in would help.
    assert (await client.post("/warehouses", json=DEPOT)).status_code == 401
