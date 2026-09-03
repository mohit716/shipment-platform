import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

LEEDS = {"code": "LDS1", "name": "Leeds Central Depot", "city": "Leeds"}


async def test_registering_a_warehouse(client: AsyncClient) -> None:
    response = await client.post("/warehouses", json=LEEDS)
    assert response.status_code == 201
    assert response.json()["code"] == "LDS1"


async def test_depot_codes_are_normalised_to_upper_case(client: AsyncClient) -> None:
    response = await client.post("/warehouses", json={**LEEDS, "code": " lds1 "})
    assert response.json()["code"] == "LDS1"


async def test_duplicate_depot_code_is_rejected(client: AsyncClient) -> None:
    await client.post("/warehouses", json=LEEDS)
    # Lower case, but normalisation makes it the same code.
    response = await client.post("/warehouses", json={**LEEDS, "code": "lds1"})
    assert response.status_code == 409


async def test_warehouses_can_be_filtered_by_city(client: AsyncClient) -> None:
    await client.post("/warehouses", json=LEEDS)
    await client.post(
        "/warehouses",
        json={"code": "NCL1", "name": "Newcastle Hub", "city": "Newcastle"},
    )
    results = (await client.get("/warehouses", params={"city": "Leeds"})).json()
    assert [w["code"] for w in results] == ["LDS1"]


async def test_reading_a_missing_warehouse_returns_404(client: AsyncClient) -> None:
    assert (await client.get("/warehouses/4242")).status_code == 404
