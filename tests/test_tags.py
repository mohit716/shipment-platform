import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

BOOKING = {"content": "ceramic dinnerware", "weight_kg": 2.4, "destination": 11001}


async def book(client: AsyncClient, email: str = "tags@example.com") -> int:
    customer = (
        await client.post(
            "/users",
            json={
                "email": email,
                "full_name": "Ada Lovelace",
                "password": "correct-horse",
            },
        )
    ).json()
    shipment = (
        await client.post(
            "/shipments", json={**BOOKING, "customer_id": customer["id"]}
        )
    ).json()
    return shipment["id"]


async def make_tag(client: AsyncClient, name: str, signature: bool = False) -> int:
    response = await client.post(
        "/tags", json={"name": name, "requires_signature": signature}
    )
    return response.json()["id"]


async def test_tag_names_are_normalised(client: AsyncClient) -> None:
    response = await client.post("/tags", json={"name": "  FRAGILE  "})
    assert response.json()["name"] == "fragile"


async def test_duplicate_tag_names_are_rejected(client: AsyncClient) -> None:
    await make_tag(client, "fragile")
    response = await client.post("/tags", json={"name": "Fragile"})
    assert response.status_code == 409


async def test_applying_tags_to_a_shipment(client: AsyncClient) -> None:
    shipment_id = await book(client)
    fragile = await make_tag(client, "fragile", signature=True)
    perishable = await make_tag(client, "perishable")

    await client.put(f"/shipments/{shipment_id}/tags/{fragile}")
    response = await client.put(f"/shipments/{shipment_id}/tags/{perishable}")

    assert {t["name"] for t in response.json()} == {"fragile", "perishable"}


async def test_a_tag_is_shared_across_shipments(client: AsyncClient) -> None:
    first = await book(client, "one@example.com")
    second = await book(client, "two@example.com")
    fragile = await make_tag(client, "fragile")

    await client.put(f"/shipments/{first}/tags/{fragile}")
    await client.put(f"/shipments/{second}/tags/{fragile}")

    assert (await client.get(f"/shipments/{first}/tags")).json()[0]["id"] == fragile
    assert (await client.get(f"/shipments/{second}/tags")).json()[0]["id"] == fragile


async def test_removing_a_tag_leaves_it_in_the_vocabulary(client: AsyncClient) -> None:
    shipment_id = await book(client)
    fragile = await make_tag(client, "fragile")
    await client.put(f"/shipments/{shipment_id}/tags/{fragile}")

    assert (await client.delete(f"/shipments/{shipment_id}/tags/{fragile}")).json() == []
    assert [t["name"] for t in (await client.get("/tags")).json()] == ["fragile"]


async def test_applying_an_unknown_tag_returns_404(client: AsyncClient) -> None:
    shipment_id = await book(client)
    assert (await client.put(f"/shipments/{shipment_id}/tags/4242")).status_code == 404
