import pytest
from httpx import AsyncClient

# Applies the anyio marker to every test in the module, so each one no longer
# needs its own decorator.
pytestmark = pytest.mark.anyio

VALID_BOOKING = {
    "content": "ceramic dinnerware",
    "weight_kg": 2.4,
    "destination": 11001,
}


async def book(client: AsyncClient, **overrides: object) -> dict:
    response = await client.post("/shipments", json={**VALID_BOOKING, **overrides})
    assert response.status_code == 201
    return response.json()


async def test_health_reports_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_booking_assigns_an_id_and_defaults_to_placed(
    client: AsyncClient,
) -> None:
    created = await book(client)
    assert created["id"] >= 1
    assert created["status"] == "placed"


async def test_booking_normalises_whitespace_in_content(client: AsyncClient) -> None:
    created = await book(client, content="  ceramic   dinnerware  ")
    assert created["content"] == "ceramic dinnerware"


async def test_listing_starts_empty_then_reflects_bookings(
    client: AsyncClient,
) -> None:
    assert (await client.get("/shipments")).json() == []
    await book(client)
    await book(client, content="laptop parts")
    assert len((await client.get("/shipments")).json()) == 2


async def test_reading_a_missing_shipment_returns_404(client: AsyncClient) -> None:
    response = await client.get("/shipments/4242")
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


async def test_patch_changes_only_the_supplied_field(client: AsyncClient) -> None:
    created = await book(client)
    response = await client.patch(
        f"/shipments/{created['id']}", json={"status": "in_transit"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "in_transit"
    assert updated["content"] == created["content"]
    assert updated["weight_kg"] == created["weight_kg"]


async def test_put_replaces_and_resets_omitted_fields(client: AsyncClient) -> None:
    created = await book(client, status="in_transit")
    response = await client.put(f"/shipments/{created['id']}", json=VALID_BOOKING)
    # status was omitted from the body, so it falls back to the schema default.
    assert response.json()["status"] == "placed"


async def test_delete_removes_the_shipment(client: AsyncClient) -> None:
    created = await book(client)
    assert (await client.delete(f"/shipments/{created['id']}")).status_code == 204
    assert (await client.get(f"/shipments/{created['id']}")).status_code == 404


async def test_overweight_parcel_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/shipments", json={**VALID_BOOKING, "weight_kg": 90})
    assert response.status_code == 422


async def test_prohibited_content_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/shipments", json={**VALID_BOOKING, "content": "firearm parts"}
    )
    assert response.status_code == 422


async def test_unknown_status_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/shipments", json={**VALID_BOOKING, "status": "delivrd"}
    )
    assert response.status_code == 422


async def test_status_filter_narrows_the_list(client: AsyncClient) -> None:
    await book(client)
    moving = await book(client, status="in_transit")
    response = await client.get("/shipments", params={"status": "in_transit"})
    assert [row["id"] for row in response.json()] == [moving["id"]]


async def test_limit_caps_the_page_size(client: AsyncClient) -> None:
    for _ in range(3):
        await book(client)
    assert len((await client.get("/shipments", params={"limit": 2})).json()) == 2
    assert (await client.get("/shipments", params={"limit": 500})).status_code == 422


async def test_carrier_quotes_run_concurrently(client: AsyncClient) -> None:
    response = await client.get("/shipments/quotes", params={"weight_kg": 3})
    assert response.status_code == 200
    payload = response.json()
    # The whole point of gather: elapsed time tracks the slowest call, not the sum.
    assert payload["elapsed_seconds"] < payload["sequential_would_take"]
    prices = [quote["price"] for quote in payload["quotes"]]
    assert prices == sorted(prices)
