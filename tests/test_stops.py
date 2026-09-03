import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

BOOKING = {"content": "ceramic dinnerware", "weight_kg": 2.4, "destination": 11001}


async def setup_shipment_and_depots(staff_client: AsyncClient) -> tuple[int, int, int]:
    shipment = (await staff_client.post("/shipments", json=BOOKING)).json()
    leeds = (
        await staff_client.post(
            "/warehouses",
            json={"code": "LDS1", "name": "Leeds Central", "city": "Leeds"},
        )
    ).json()
    newcastle = (
        await staff_client.post(
            "/warehouses",
            json={"code": "NCL1", "name": "Newcastle Hub", "city": "Newcastle"},
        )
    ).json()
    return shipment["id"], leeds["id"], newcastle["id"]


async def test_a_shipment_starts_with_no_stops(staff_client: AsyncClient) -> None:
    shipment_id, _, _ = await setup_shipment_and_depots(staff_client)
    assert (await staff_client.get(f"/shipments/{shipment_id}/stops")).json() == []


async def test_attaching_stops_builds_a_route(staff_client: AsyncClient) -> None:
    shipment_id, leeds, newcastle = await setup_shipment_and_depots(staff_client)

    await staff_client.put(f"/shipments/{shipment_id}/stops/{leeds}")
    response = await staff_client.put(f"/shipments/{shipment_id}/stops/{newcastle}")

    assert response.status_code == 200
    assert {w["code"] for w in response.json()} == {"LDS1", "NCL1"}


async def test_attaching_the_same_stop_twice_is_idempotent(
    staff_client: AsyncClient,
) -> None:
    shipment_id, leeds, _ = await setup_shipment_and_depots(staff_client)

    await staff_client.put(f"/shipments/{shipment_id}/stops/{leeds}")
    response = await staff_client.put(f"/shipments/{shipment_id}/stops/{leeds}")

    # Without the membership check this would violate the link table's
    # composite primary key.
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_detaching_a_stop_leaves_the_warehouse_intact(
    staff_client: AsyncClient,
) -> None:
    shipment_id, leeds, newcastle = await setup_shipment_and_depots(staff_client)
    await staff_client.put(f"/shipments/{shipment_id}/stops/{leeds}")
    await staff_client.put(f"/shipments/{shipment_id}/stops/{newcastle}")

    response = await staff_client.delete(f"/shipments/{shipment_id}/stops/{leeds}")
    assert [w["code"] for w in response.json()] == ["NCL1"]

    # Only the link row was deleted; the depot is a shared entity.
    assert (await staff_client.get(f"/warehouses/{leeds}")).status_code == 200


async def test_the_same_warehouse_serves_many_shipments(staff_client: AsyncClient) -> None:
    first_id, leeds, _ = await setup_shipment_and_depots(staff_client)
    second = (await staff_client.post("/shipments", json=BOOKING)).json()

    await staff_client.put(f"/shipments/{first_id}/stops/{leeds}")
    await staff_client.put(f"/shipments/{second['id']}/stops/{leeds}")

    assert len((await staff_client.get(f"/shipments/{first_id}/stops")).json()) == 1
    assert len((await staff_client.get(f"/shipments/{second['id']}/stops")).json()) == 1


async def test_attaching_an_unknown_warehouse_returns_404(
    staff_client: AsyncClient,
) -> None:
    shipment_id, _, _ = await setup_shipment_and_depots(staff_client)
    assert (await staff_client.put(f"/shipments/{shipment_id}/stops/4242")).status_code == 404
