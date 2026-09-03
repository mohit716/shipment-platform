from fastapi.testclient import TestClient

VALID_BOOKING = {
    "content": "ceramic dinnerware",
    "weight_kg": 2.4,
    "destination": 11001,
}


def book(client: TestClient, **overrides: object) -> dict:
    response = client.post("/shipments", json={**VALID_BOOKING, **overrides})
    assert response.status_code == 201
    return response.json()


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_booking_assigns_an_id_and_defaults_to_placed(client: TestClient) -> None:
    created = book(client)
    assert created["id"] >= 1
    assert created["status"] == "placed"


def test_booking_normalises_whitespace_in_content(client: TestClient) -> None:
    created = book(client, content="  ceramic   dinnerware  ")
    assert created["content"] == "ceramic dinnerware"


def test_listing_starts_empty_then_reflects_bookings(client: TestClient) -> None:
    assert client.get("/shipments").json() == []
    book(client)
    book(client, content="laptop parts")
    assert len(client.get("/shipments").json()) == 2


def test_reading_a_missing_shipment_returns_404(client: TestClient) -> None:
    response = client.get("/shipments/4242")
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_patch_changes_only_the_supplied_field(client: TestClient) -> None:
    created = book(client)
    response = client.patch(
        f"/shipments/{created['id']}", json={"status": "in_transit"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "in_transit"
    assert updated["content"] == created["content"]
    assert updated["weight_kg"] == created["weight_kg"]


def test_put_replaces_and_resets_omitted_fields(client: TestClient) -> None:
    created = book(client, status="in_transit")
    response = client.put(f"/shipments/{created['id']}", json=VALID_BOOKING)
    # status was omitted from the body, so it falls back to the schema default.
    assert response.json()["status"] == "placed"


def test_delete_removes_the_shipment(client: TestClient) -> None:
    created = book(client)
    assert client.delete(f"/shipments/{created['id']}").status_code == 204
    assert client.get(f"/shipments/{created['id']}").status_code == 404


def test_overweight_parcel_is_rejected(client: TestClient) -> None:
    response = client.post("/shipments", json={**VALID_BOOKING, "weight_kg": 90})
    assert response.status_code == 422


def test_prohibited_content_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/shipments", json={**VALID_BOOKING, "content": "firearm parts"}
    )
    assert response.status_code == 422


def test_unknown_status_is_rejected(client: TestClient) -> None:
    response = client.post("/shipments", json={**VALID_BOOKING, "status": "delivrd"})
    assert response.status_code == 422


def test_status_filter_narrows_the_list(client: TestClient) -> None:
    book(client)
    moving = book(client, status="in_transit")
    results = client.get("/shipments", params={"status": "in_transit"}).json()
    assert [row["id"] for row in results] == [moving["id"]]


def test_limit_caps_the_page_size(client: TestClient) -> None:
    for _ in range(3):
        book(client)
    assert len(client.get("/shipments", params={"limit": 2}).json()) == 2
    assert client.get("/shipments", params={"limit": 500}).status_code == 422
