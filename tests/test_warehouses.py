import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

LEEDS = {"code": "LDS1", "name": "Leeds Central Depot", "city": "Leeds"}


async def test_registering_a_warehouse(staff_client: AsyncClient) -> None:
    response = await staff_client.post("/warehouses", json=LEEDS)
    assert response.status_code == 201
    assert response.json()["code"] == "LDS1"


async def test_depot_codes_are_normalised_to_upper_case(staff_client: AsyncClient) -> None:
    response = await staff_client.post("/warehouses", json={**LEEDS, "code": " lds1 "})
    assert response.json()["code"] == "LDS1"


async def test_duplicate_depot_code_is_rejected(staff_client: AsyncClient) -> None:
    await staff_client.post("/warehouses", json=LEEDS)
    # Lower case, but normalisation makes it the same code.
    response = await staff_client.post("/warehouses", json={**LEEDS, "code": "lds1"})
    assert response.status_code == 409


async def test_warehouses_can_be_filtered_by_city(staff_client: AsyncClient) -> None:
    await staff_client.post("/warehouses", json=LEEDS)
    await staff_client.post(
        "/warehouses",
        json={"code": "NCL1", "name": "Newcastle Hub", "city": "Newcastle"},
    )
    results = (await staff_client.get("/warehouses", params={"city": "Leeds"})).json()
    assert [w["code"] for w in results] == ["LDS1"]


async def test_reading_a_missing_warehouse_returns_404(staff_client: AsyncClient) -> None:
    assert (await staff_client.get("/warehouses/4242")).status_code == 404
