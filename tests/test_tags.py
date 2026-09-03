import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

BOOKING = {"content": "ceramic dinnerware", "weight_kg": 2.4, "destination": 11001}


async def book(staff_client: AsyncClient) -> int:
    shipment = (await staff_client.post("/shipments", json=BOOKING)).json()
    return shipment["id"]


async def make_tag(staff_client: AsyncClient, name: str, signature: bool = False) -> int:
    response = await staff_client.post(
        "/tags", json={"name": name, "requires_signature": signature}
    )
    return response.json()["id"]


async def test_tag_names_are_normalised(staff_client: AsyncClient) -> None:
    response = await staff_client.post("/tags", json={"name": "  FRAGILE  "})
    assert response.json()["name"] == "fragile"


async def test_duplicate_tag_names_are_rejected(staff_client: AsyncClient) -> None:
    await make_tag(staff_client, "fragile")
    response = await staff_client.post("/tags", json={"name": "Fragile"})
    assert response.status_code == 409


async def test_applying_tags_to_a_shipment(staff_client: AsyncClient) -> None:
    shipment_id = await book(staff_client)
    fragile = await make_tag(staff_client, "fragile", signature=True)
    perishable = await make_tag(staff_client, "perishable")

    await staff_client.put(f"/shipments/{shipment_id}/tags/{fragile}")
    response = await staff_client.put(f"/shipments/{shipment_id}/tags/{perishable}")

    assert {t["name"] for t in response.json()} == {"fragile", "perishable"}


async def test_a_tag_is_shared_across_shipments(staff_client: AsyncClient) -> None:
    first = await book(staff_client)
    second = await book(staff_client)
    fragile = await make_tag(staff_client, "fragile")

    await staff_client.put(f"/shipments/{first}/tags/{fragile}")
    await staff_client.put(f"/shipments/{second}/tags/{fragile}")

    assert (await staff_client.get(f"/shipments/{first}/tags")).json()[0]["id"] == fragile
    assert (await staff_client.get(f"/shipments/{second}/tags")).json()[0]["id"] == fragile


async def test_removing_a_tag_leaves_it_in_the_vocabulary(staff_client: AsyncClient) -> None:
    shipment_id = await book(staff_client)
    fragile = await make_tag(staff_client, "fragile")
    await staff_client.put(f"/shipments/{shipment_id}/tags/{fragile}")

    assert (await staff_client.delete(f"/shipments/{shipment_id}/tags/{fragile}")).json() == []
    assert [t["name"] for t in (await staff_client.get("/tags")).json()] == ["fragile"]


async def test_applying_an_unknown_tag_returns_404(staff_client: AsyncClient) -> None:
    shipment_id = await book(staff_client)
    assert (await staff_client.put(f"/shipments/{shipment_id}/tags/4242")).status_code == 404
