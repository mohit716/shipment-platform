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


async def register(client: AsyncClient, email: str = "ada@example.com") -> dict:
    response = await client.post(
        "/users", json={"email": email, "full_name": "Ada Lovelace"}
    )
    assert response.status_code == 201
    return response.json()


async def book(client: AsyncClient, **overrides: object) -> dict:
    """Book a shipment, registering a customer first if none was supplied."""
    if "customer_id" not in overrides:
        overrides["customer_id"] = (await register(client, _unique_email()))["id"]
    response = await client.post("/shipments", json={**VALID_BOOKING, **overrides})
    assert response.status_code == 201
    return response.json()


_email_counter = 0


def _unique_email() -> str:
    global _email_counter
    _email_counter += 1
    return f"customer{_email_counter}@example.com"


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


async def test_detail_view_embeds_the_customer(client: AsyncClient) -> None:
    customer = await register(client, "embedded@example.com")
    created = await book(client, customer_id=customer["id"])

    response = await client.get(f"/shipments/{created['id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["customer"]["id"] == customer["id"]
    assert payload["customer"]["full_name"] == "Ada Lovelace"
    # The nested summary is deliberately narrow: no email, no created_at.
    assert "email" not in payload["customer"]


async def test_list_view_does_not_embed_the_customer(client: AsyncClient) -> None:
    await book(client)
    row = (await client.get("/shipments")).json()[0]
    assert "customer_id" in row
    assert "customer" not in row


BOX = {
    "description": "outer carton",
    "weight_kg": 2.4,
    "length_cm": 40,
    "width_cm": 30,
    "height_cm": 20,
}


async def test_booking_creates_nested_packages(client: AsyncClient) -> None:
    created = await book(client, packages=[BOX, {**BOX, "description": "spares box"}])
    detail = (await client.get(f"/shipments/{created['id']}")).json()

    assert len(detail["packages"]) == 2
    assert {p["description"] for p in detail["packages"]} == {
        "outer carton",
        "spares box",
    }
    # Every child was given the parent's id without the client supplying it.
    assert all(p["shipment_id"] == created["id"] for p in detail["packages"])


async def test_volumetric_weight_is_derived_from_dimensions(
    client: AsyncClient,
) -> None:
    created = await book(client, packages=[BOX])
    package = (await client.get(f"/shipments/{created['id']}")).json()["packages"][0]
    # 40 * 30 * 20 / 5000
    assert package["volumetric_weight_kg"] == 4.8


async def test_deleting_a_shipment_removes_its_packages(client: AsyncClient) -> None:
    created = await book(client, packages=[BOX])
    assert (await client.delete(f"/shipments/{created['id']}")).status_code == 204
    assert (await client.get(f"/shipments/{created['id']}")).status_code == 404


async def test_put_replaces_the_package_list(client: AsyncClient) -> None:
    created = await book(client, packages=[BOX, {**BOX, "description": "spares box"}])
    response = await client.put(
        f"/shipments/{created['id']}",
        json={
            **VALID_BOOKING,
            "customer_id": created["customer_id"],
            "packages": [{**BOX, "description": "single replacement carton"}],
        },
    )
    assert response.status_code == 200
    packages = response.json()["packages"]
    # The two originals were orphaned by the replacement and deleted.
    assert [p["description"] for p in packages] == ["single replacement carton"]


async def test_a_shipment_may_have_no_packages(client: AsyncClient) -> None:
    created = await book(client)
    detail = (await client.get(f"/shipments/{created['id']}")).json()
    assert detail["packages"] == []


async def test_invalid_package_dimensions_are_rejected(client: AsyncClient) -> None:
    customer = await register(client, "boxes@example.com")
    response = await client.post(
        "/shipments",
        json={
            **VALID_BOOKING,
            "customer_id": customer["id"],
            "packages": [{**BOX, "height_cm": 0}],
        },
    )
    assert response.status_code == 422


async def test_tracking_timeline_starts_empty(client: AsyncClient) -> None:
    created = await book(client)
    response = await client.get(f"/shipments/{created['id']}/tracking")
    assert response.status_code == 200
    assert response.json() == []


async def test_recording_a_scan_advances_the_shipment_status(
    client: AsyncClient,
) -> None:
    created = await book(client)
    assert created["status"] == "placed"

    response = await client.post(
        f"/shipments/{created['id']}/tracking",
        json={"status": "picked_up", "location": "Leeds depot"},
    )
    assert response.status_code == 201
    assert response.json()["location"] == "Leeds depot"

    # The summary follows the scan, in the same transaction.
    detail = (await client.get(f"/shipments/{created['id']}")).json()
    assert detail["status"] == "picked_up"


async def test_timeline_is_returned_in_chronological_order(
    client: AsyncClient,
) -> None:
    created = await book(client)
    for status_value, location in [
        ("picked_up", "Leeds depot"),
        ("in_transit", "M1 northbound"),
        ("at_warehouse", "Newcastle hub"),
        ("delivered", "customer address"),
    ]:
        await client.post(
            f"/shipments/{created['id']}/tracking",
            json={"status": status_value, "location": location},
        )

    timeline = (await client.get(f"/shipments/{created['id']}/tracking")).json()
    assert [event["status"] for event in timeline] == [
        "picked_up",
        "in_transit",
        "at_warehouse",
        "delivered",
    ]
    timestamps = [event["recorded_at"] for event in timeline]
    assert timestamps == sorted(timestamps)


async def test_deleting_a_shipment_removes_its_tracking_events(
    client: AsyncClient,
) -> None:
    created = await book(client)
    await client.post(
        f"/shipments/{created['id']}/tracking",
        json={"status": "picked_up", "location": "Leeds depot"},
    )
    assert (await client.delete(f"/shipments/{created['id']}")).status_code == 204
    assert (await client.get(f"/shipments/{created['id']}/tracking")).status_code == 404


async def test_scanning_an_unknown_shipment_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/shipments/4242/tracking",
        json={"status": "picked_up", "location": "Leeds depot"},
    )
    assert response.status_code == 404


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
    response = await client.put(
        f"/shipments/{created['id']}",
        json={**VALID_BOOKING, "customer_id": created["customer_id"]},
    )
    # status was omitted from the body, so it falls back to the schema default.
    assert response.json()["status"] == "placed"


async def test_delete_removes_the_shipment(client: AsyncClient) -> None:
    created = await book(client)
    assert (await client.delete(f"/shipments/{created['id']}")).status_code == 204
    assert (await client.get(f"/shipments/{created['id']}")).status_code == 404


async def test_overweight_parcel_is_rejected(client: AsyncClient) -> None:
    customer = await register(client)
    response = await client.post(
        "/shipments",
        json={**VALID_BOOKING, "customer_id": customer["id"], "weight_kg": 90},
    )
    assert response.status_code == 422


async def test_prohibited_content_is_rejected(client: AsyncClient) -> None:
    customer = await register(client)
    response = await client.post(
        "/shipments",
        json={**VALID_BOOKING, "customer_id": customer["id"], "content": "firearm parts"},
    )
    assert response.status_code == 422


async def test_unknown_status_is_rejected(client: AsyncClient) -> None:
    customer = await register(client)
    response = await client.post(
        "/shipments",
        json={**VALID_BOOKING, "customer_id": customer["id"], "status": "delivrd"},
    )
    assert response.status_code == 422


async def test_booking_for_an_unknown_customer_is_rejected(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/shipments", json={**VALID_BOOKING, "customer_id": 9999}
    )
    assert response.status_code == 404
    assert "Customer 9999" in response.json()["detail"]


async def test_shipments_can_be_filtered_by_customer(client: AsyncClient) -> None:
    first = await book(client)
    await book(client)
    response = await client.get(
        "/shipments", params={"customer_id": first["customer_id"]}
    )
    assert [row["id"] for row in response.json()] == [first["id"]]


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
