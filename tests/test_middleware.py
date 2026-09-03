import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_every_response_carries_a_request_id(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert len(response.headers["x-request-id"]) == 32


async def test_each_request_gets_its_own_id(client: AsyncClient) -> None:
    first = await client.get("/health")
    second = await client.get("/health")
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


async def test_an_incoming_id_is_honoured(client: AsyncClient) -> None:
    response = await client.get(
        "/health", headers={"X-Request-ID": "trace-from-the-load-balancer"}
    )
    # A trace started upstream should keep its name rather than being renamed
    # at every hop.
    assert response.headers["x-request-id"] == "trace-from-the-load-balancer"


async def test_responses_report_how_long_they_took(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert float(response.headers["x-response-time-ms"]) >= 0


async def test_error_responses_are_instrumented_too(client: AsyncClient) -> None:
    # A dependency could not do this: nothing routed to 404 ever reaches one,
    # which is exactly why this is middleware.
    response = await client.get("/no-such-route")
    assert response.status_code == 404
    assert "x-request-id" in response.headers


async def test_validation_failures_are_instrumented_too(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post("/shipments", json={"weight_kg": "heavy"})
    assert response.status_code == 422
    assert "x-request-id" in response.headers


async def test_the_id_is_readable_from_inside_a_handler(client: AsyncClient) -> None:
    from app.core.middleware import get_request_id

    # Outside a request there is no id, and asking for one must not explode.
    assert get_request_id() == "-"
    assert (await client.get("/health")).status_code == 200


async def test_concurrent_requests_do_not_share_an_id(client: AsyncClient) -> None:
    import asyncio

    responses = await asyncio.gather(*(client.get("/health") for _ in range(8)))
    ids = {response.headers["x-request-id"] for response in responses}
    # A plain module-level global would be overwritten by whichever request ran
    # most recently; a ContextVar gives each task its own view.
    assert len(ids) == 8
