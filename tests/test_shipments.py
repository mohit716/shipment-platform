import pytest
from httpx import AsyncClient

from tests.conftest import login_as
from tests.factories import BOOKING as VALID_BOOKING
from tests.factories import book

# Applies the anyio marker to every test in the module, so each one no longer
# needs its own decorator.
pytestmark = pytest.mark.anyio


async def test_health_reports_ok(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_booking_assigns_an_id_and_defaults_to_placed(
    auth_client: AsyncClient,
) -> None:
    created = await book(auth_client)
    assert created["id"] >= 1
    assert created["status"] == "placed"


async def test_booking_normalises_whitespace_in_content(auth_client: AsyncClient) -> None:
    created = await book(auth_client, content="  ceramic   dinnerware  ")
    assert created["content"] == "ceramic dinnerware"


async def test_listing_starts_empty_then_reflects_bookings(
    auth_client: AsyncClient,
) -> None:
    assert (await auth_client.get("/shipments")).json() == []
    await book(auth_client)
    await book(auth_client, content="laptop parts")
    assert len((await auth_client.get("/shipments")).json()) == 2


async def test_detail_view_embeds_the_customer(
    auth_client: AsyncClient, customer: dict
) -> None:
    created = await book(auth_client)

    response = await auth_client.get(f"/shipments/{created['id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["customer"]["id"] == customer["id"]
    assert payload["customer"]["full_name"] == "Ada Lovelace"
    # The nested summary is deliberately narrow: no email, no created_at.
    assert "email" not in payload["customer"]


async def test_list_view_does_not_embed_the_customer(auth_client: AsyncClient) -> None:
    await book(auth_client)
    row = (await auth_client.get("/shipments")).json()[0]
    assert "customer_id" in row
    assert "customer" not in row


BOX = {
    "description": "outer carton",
    "weight_kg": 2.4,
    "length_cm": 40,
    "width_cm": 30,
    "height_cm": 20,
}


async def test_booking_creates_nested_packages(auth_client: AsyncClient) -> None:
    created = await book(auth_client, packages=[BOX, {**BOX, "description": "spares box"}])
    detail = (await auth_client.get(f"/shipments/{created['id']}")).json()

    assert len(detail["packages"]) == 2
    assert {p["description"] for p in detail["packages"]} == {
        "outer carton",
        "spares box",
    }
    # Every child was given the parent's id without the auth_client supplying it.
    assert all(p["shipment_id"] == created["id"] for p in detail["packages"])


async def test_volumetric_weight_is_derived_from_dimensions(
    auth_client: AsyncClient,
) -> None:
    created = await book(auth_client, packages=[BOX])
    package = (await auth_client.get(f"/shipments/{created['id']}")).json()["packages"][0]
    # 40 * 30 * 20 / 5000
    assert package["volumetric_weight_kg"] == 4.8


async def test_deleting_a_shipment_removes_its_packages(auth_client: AsyncClient) -> None:
    created = await book(auth_client, packages=[BOX])
    assert (await auth_client.delete(f"/shipments/{created['id']}")).status_code == 204
    assert (await auth_client.get(f"/shipments/{created['id']}")).status_code == 404


async def test_put_replaces_the_package_list(auth_client: AsyncClient) -> None:
    created = await book(auth_client, packages=[BOX, {**BOX, "description": "spares box"}])
    response = await auth_client.put(
        f"/shipments/{created['id']}",
        json={
            **VALID_BOOKING,
            "packages": [{**BOX, "description": "single replacement carton"}],
        },
    )
    assert response.status_code == 200
    packages = response.json()["packages"]
    # The two originals were orphaned by the replacement and deleted.
    assert [p["description"] for p in packages] == ["single replacement carton"]


async def test_a_shipment_may_have_no_packages(auth_client: AsyncClient) -> None:
    created = await book(auth_client)
    detail = (await auth_client.get(f"/shipments/{created['id']}")).json()
    assert detail["packages"] == []


async def test_invalid_package_dimensions_are_rejected(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/shipments",
        json={**VALID_BOOKING, "packages": [{**BOX, "height_cm": 0}]},
    )
    assert response.status_code == 422


async def test_tracking_timeline_starts_empty(auth_client: AsyncClient) -> None:
    created = await book(auth_client)
    response = await auth_client.get(f"/shipments/{created['id']}/tracking")
    assert response.status_code == 200
    assert response.json() == []


async def test_recording_a_scan_advances_the_shipment_status(
    staff_client: AsyncClient,
) -> None:
    created = await book(staff_client)
    assert created["status"] == "placed"

    response = await staff_client.post(
        f"/shipments/{created['id']}/tracking",
        json={"status": "picked_up", "location": "Leeds depot"},
    )
    assert response.status_code == 201
    assert response.json()["location"] == "Leeds depot"

    # The summary follows the scan, in the same transaction.
    detail = (await staff_client.get(f"/shipments/{created['id']}")).json()
    assert detail["status"] == "picked_up"


async def test_a_customer_cannot_scan_their_own_shipment(
    auth_client: AsyncClient,
) -> None:
    created = await book(auth_client)
    # A customer who can write scans can declare their own parcel delivered.
    response = await auth_client.post(
        f"/shipments/{created['id']}/tracking",
        json={"status": "delivered", "location": "wherever I say"},
    )
    assert response.status_code == 403


async def test_timeline_is_returned_in_chronological_order(
    staff_client: AsyncClient,
) -> None:
    created = await book(staff_client)
    for status_value, location in [
        ("picked_up", "Leeds depot"),
        ("in_transit", "M1 northbound"),
        ("at_warehouse", "Newcastle hub"),
        ("delivered", "customer address"),
    ]:
        await staff_client.post(
            f"/shipments/{created['id']}/tracking",
            json={"status": status_value, "location": location},
        )

    timeline = (await staff_client.get(f"/shipments/{created['id']}/tracking")).json()
    assert [event["status"] for event in timeline] == [
        "picked_up",
        "in_transit",
        "at_warehouse",
        "delivered",
    ]
    timestamps = [event["recorded_at"] for event in timeline]
    assert timestamps == sorted(timestamps)


async def test_deleting_a_shipment_removes_its_tracking_events(
    staff_client: AsyncClient,
) -> None:
    created = await book(staff_client)
    await staff_client.post(
        f"/shipments/{created['id']}/tracking",
        json={"status": "picked_up", "location": "Leeds depot"},
    )
    assert (await staff_client.delete(f"/shipments/{created['id']}")).status_code == 204
    assert (
        await staff_client.get(f"/shipments/{created['id']}/tracking")
    ).status_code == 404


async def test_scanning_an_unknown_shipment_returns_404(
    staff_client: AsyncClient,
) -> None:
    response = await staff_client.post(
        "/shipments/4242/tracking",
        json={"status": "picked_up", "location": "Leeds depot"},
    )
    assert response.status_code == 404


async def test_reading_a_missing_shipment_returns_404(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/shipments/4242")
    assert response.status_code == 404
    assert "does not exist" in response.json()["error"]["message"]


async def test_patch_changes_only_the_supplied_field(auth_client: AsyncClient) -> None:
    created = await book(auth_client)
    response = await auth_client.patch(
        f"/shipments/{created['id']}", json={"status": "in_transit"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "in_transit"
    assert updated["content"] == created["content"]
    assert updated["weight_kg"] == created["weight_kg"]


async def test_put_replaces_and_resets_omitted_fields(auth_client: AsyncClient) -> None:
    created = await book(auth_client, status="in_transit")
    response = await auth_client.put(
        f"/shipments/{created['id']}",
        json=VALID_BOOKING,
    )
    # status was omitted from the body, so it falls back to the schema default.
    assert response.json()["status"] == "placed"


async def test_delete_removes_the_shipment(auth_client: AsyncClient) -> None:
    created = await book(auth_client)
    assert (await auth_client.delete(f"/shipments/{created['id']}")).status_code == 204
    assert (await auth_client.get(f"/shipments/{created['id']}")).status_code == 404


async def test_overweight_parcel_is_rejected(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/shipments", json={**VALID_BOOKING, "weight_kg": 90}
    )
    assert response.status_code == 422


async def test_prohibited_content_is_rejected(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/shipments", json={**VALID_BOOKING, "content": "firearm parts"}
    )
    assert response.status_code == 422


async def test_unknown_status_is_rejected(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/shipments", json={**VALID_BOOKING, "status": "delivrd"}
    )
    assert response.status_code == 422


async def test_naming_a_customer_in_the_body_is_rejected(
    auth_client: AsyncClient,
) -> None:
    # extra="forbid" turns what used to be an ownership hole into a 422, rather
    # than accepting the key and quietly ignoring it.
    response = await auth_client.post(
        "/shipments", json={**VALID_BOOKING, "customer_id": 9999}
    )
    assert response.status_code == 422


async def test_a_booking_belongs_to_the_token_holder(
    auth_client: AsyncClient, customer: dict
) -> None:
    created = await book(auth_client)
    assert created["customer_id"] == customer["id"]


async def test_booking_without_a_token_is_401(client: AsyncClient) -> None:
    # The plain client fixture carries no Authorization header.
    assert (await client.post("/shipments", json=VALID_BOOKING)).status_code == 401


async def test_the_list_shows_only_your_own_shipments(
    auth_client: AsyncClient,
) -> None:
    mine = await book(auth_client)
    other = await login_as(auth_client, "grace@example.com", "Grace Hopper")
    await auth_client.post("/shipments", json=VALID_BOOKING, headers=other)

    rows = (await auth_client.get("/shipments")).json()
    assert [row["id"] for row in rows] == [mine["id"]]


async def test_another_customers_shipment_reads_as_404_not_403(
    auth_client: AsyncClient,
) -> None:
    mine = await book(auth_client)
    other = await login_as(auth_client, "grace@example.com", "Grace Hopper")

    response = await auth_client.get(f"/shipments/{mine['id']}", headers=other)
    # 403 would confirm the reference exists and let a stranger map the id
    # space by watching which numbers answer differently.
    assert response.status_code == 404


async def test_another_customer_cannot_cancel_your_shipment(
    auth_client: AsyncClient,
) -> None:
    mine = await book(auth_client)
    other = await login_as(auth_client, "grace@example.com", "Grace Hopper")

    assert (
        await auth_client.delete(f"/shipments/{mine['id']}", headers=other)
    ).status_code == 404
    # Still there for its owner.
    assert (await auth_client.get(f"/shipments/{mine['id']}")).status_code == 200


async def test_status_filter_narrows_the_list(auth_client: AsyncClient) -> None:
    await book(auth_client)
    moving = await book(auth_client, status="in_transit")
    response = await auth_client.get("/shipments", params={"status": "in_transit"})
    assert [row["id"] for row in response.json()] == [moving["id"]]


async def test_limit_caps_the_page_size(auth_client: AsyncClient) -> None:
    for _ in range(3):
        await book(auth_client)
    assert len((await auth_client.get("/shipments", params={"limit": 2})).json()) == 2
    assert (await auth_client.get("/shipments", params={"limit": 500})).status_code == 422


async def test_carrier_quotes_run_concurrently(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/shipments/quotes", params={"weight_kg": 3})
    assert response.status_code == 200
    payload = response.json()
    # The whole point of gather: elapsed time tracks the slowest call, not the sum.
    assert payload["elapsed_seconds"] < payload["sequential_would_take"]
    prices = [quote["price"] for quote in payload["quotes"]]
    assert prices == sorted(prices)
