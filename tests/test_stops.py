import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

BOOKING = {"content": "ceramic dinnerware", "weight_kg": 2.4, "destination": 11001}


async def setup_shipment_and_depots(auth_client: AsyncClient) -> tuple[int, int, int]:
    shipment = (await auth_client.post("/shipments", json=BOOKING)).json()
    leeds = (
        await auth_client.post(
            "/warehouses",
            json={"code": "LDS1", "name": "Leeds Central", "city": "Leeds"},
        )
    ).json()
    newcastle = (
        await auth_client.post(
            "/warehouses",
            json={"code": "NCL1", "name": "Newcastle Hub", "city": "Newcastle"},
        )
    ).json()
    return shipment["id"], leeds["id"], newcastle["id"]


async def test_a_shipment_starts_with_no_stops(auth_client: AsyncClient) -> None:
    shipment_id, _, _ = await setup_shipment_and_depots(auth_client)
    assert (await auth_client.get(f"/shipments/{shipment_id}/stops")).json() == []


async def test_attaching_stops_builds_a_route(auth_client: AsyncClient) -> None:
    shipment_id, leeds, newcastle = await setup_shipment_and_depots(auth_client)

    await auth_client.put(f"/shipments/{shipment_id}/stops/{leeds}")
    response = await auth_client.put(f"/shipments/{shipment_id}/stops/{newcastle}")

    assert response.status_code == 200
    assert {w["code"] for w in response.json()} == {"LDS1", "NCL1"}


async def test_attaching_the_same_stop_twice_is_idempotent(
    auth_client: AsyncClient,
) -> None:
    shipment_id, leeds, _ = await setup_shipment_and_depots(auth_client)

    await auth_client.put(f"/shipments/{shipment_id}/stops/{leeds}")
    response = await auth_client.put(f"/shipments/{shipment_id}/stops/{leeds}")

    # Without the membership check this would violate the link table's
    # composite primary key.
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_detaching_a_stop_leaves_the_warehouse_intact(
    auth_client: AsyncClient,
) -> None:
    shipment_id, leeds, newcastle = await setup_shipment_and_depots(auth_client)
    await auth_client.put(f"/shipments/{shipment_id}/stops/{leeds}")
    await auth_client.put(f"/shipments/{shipment_id}/stops/{newcastle}")

    response = await auth_client.delete(f"/shipments/{shipment_id}/stops/{leeds}")
    assert [w["code"] for w in response.json()] == ["NCL1"]

    # Only the link row was deleted; the depot is a shared entity.
    assert (await auth_client.get(f"/warehouses/{leeds}")).status_code == 200


async def test_the_same_warehouse_serves_many_shipments(auth_client: AsyncClient) -> None:
    first_id, leeds, _ = await setup_shipment_and_depots(auth_client)
    second = (await auth_client.post("/shipments", json=BOOKING)).json()

    await auth_client.put(f"/shipments/{first_id}/stops/{leeds}")
    await auth_client.put(f"/shipments/{second['id']}/stops/{leeds}")

    assert len((await auth_client.get(f"/shipments/{first_id}/stops")).json()) == 1
    assert len((await auth_client.get(f"/shipments/{second['id']}/stops")).json()) == 1


async def test_attaching_an_unknown_warehouse_returns_404(
    auth_client: AsyncClient,
) -> None:
    shipment_id, _, _ = await setup_shipment_and_depots(auth_client)
    assert (await auth_client.put(f"/shipments/{shipment_id}/stops/4242")).status_code == 404
