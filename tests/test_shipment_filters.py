import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

BOOKING = {"content": "ceramic dinnerware", "weight_kg": 2.4, "destination": 11001}


@pytest.fixture
async def routed_shipments(staff_client: AsyncClient) -> dict[str, int]:
    """Three shipments with overlapping tags and depots.

    Overlap is what makes the joins worth testing: with disjoint data almost
    any query shape passes.
    """
    async def book() -> int:
        response = await staff_client.post("/shipments", json=BOOKING)
        return response.json()["id"]

    async def tag(name: str) -> int:
        return (await staff_client.post("/tags", json={"name": name})).json()["id"]

    async def depot(code: str, city: str) -> int:
        return (
            await staff_client.post(
                "/warehouses", json={"code": code, "name": f"{city} Hub", "city": city}
            )
        ).json()["id"]

    first, second, third = await book(), await book(), await book()
    fragile, perishable = await tag("fragile"), await tag("perishable")
    leeds, newcastle = await depot("LDS1", "Leeds"), await depot("NCL1", "Newcastle")

    # first:  fragile + perishable, routed via Leeds
    # second: fragile only,         routed via Leeds and Newcastle
    # third:  no tags,              routed via Newcastle
    await staff_client.put(f"/shipments/{first}/tags/{fragile}")
    await staff_client.put(f"/shipments/{first}/tags/{perishable}")
    await staff_client.put(f"/shipments/{first}/stops/{leeds}")
    await staff_client.put(f"/shipments/{second}/tags/{fragile}")
    await staff_client.put(f"/shipments/{second}/stops/{leeds}")
    await staff_client.put(f"/shipments/{second}/stops/{newcastle}")
    await staff_client.put(f"/shipments/{third}/stops/{newcastle}")

    return {"first": first, "second": second, "third": third}


async def test_filtering_by_one_tag(
    staff_client: AsyncClient, routed_shipments: dict[str, int]
) -> None:
    results = (await staff_client.get("/shipments", params={"tag": "fragile"})).json()
    assert {s["id"] for s in results} == {
        routed_shipments["first"],
        routed_shipments["second"],
    }


async def test_repeated_tags_are_combined_with_and(
    staff_client: AsyncClient, routed_shipments: dict[str, int]
) -> None:
    results = (
        await staff_client.get("/shipments", params={"tag": ["fragile", "perishable"]})
    ).json()
    # Only the first carries both. An IN-style filter would have returned two.
    assert [s["id"] for s in results] == [routed_shipments["first"]]


async def test_filtering_by_depot(
    staff_client: AsyncClient, routed_shipments: dict[str, int]
) -> None:
    results = (await staff_client.get("/shipments", params={"depot": "LDS1"})).json()
    assert {s["id"] for s in results} == {
        routed_shipments["first"],
        routed_shipments["second"],
    }


async def test_depot_filter_is_case_insensitive(
    staff_client: AsyncClient, routed_shipments: dict[str, int]
) -> None:
    results = (await staff_client.get("/shipments", params={"depot": "lds1"})).json()
    assert len(results) == 2


async def test_a_shipment_on_two_routes_is_not_duplicated(
    staff_client: AsyncClient, routed_shipments: dict[str, int]
) -> None:
    # The second shipment has two stops; joining must not return it twice.
    results = (await staff_client.get("/shipments", params={"depot": "NCL1"})).json()
    ids = [s["id"] for s in results]
    assert len(ids) == len(set(ids))


async def test_tag_and_depot_filters_stack(
    staff_client: AsyncClient, routed_shipments: dict[str, int]
) -> None:
    results = (
        await staff_client.get(
            "/shipments", params={"tag": "perishable", "depot": "LDS1"}
        )
    ).json()
    assert [s["id"] for s in results] == [routed_shipments["first"]]


async def test_an_unused_tag_matches_nothing(
    staff_client: AsyncClient, routed_shipments: dict[str, int]
) -> None:
    assert (await staff_client.get("/shipments", params={"tag": "hazardous"})).json() == []
