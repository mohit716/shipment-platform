import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_a_404_uses_the_standard_shape(auth_client: AsyncClient) -> None:
    body = (await auth_client.get("/shipments/4242")).json()
    assert set(body["error"]) >= {"message", "request_id"}


async def test_an_unmatched_route_uses_the_same_shape(client: AsyncClient) -> None:
    # Raised by Starlette rather than FastAPI, which is why the handler is
    # registered against Starlette's exception class.
    body = (await client.get("/no-such-route")).json()
    assert "message" in body["error"]


async def test_validation_errors_use_the_same_shape(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/shipments", json={"weight_kg": 90})
    body = response.json()

    assert response.status_code == 422
    # FastAPI's default puts a list under "detail" here and a string under
    # "detail" for an HTTPException, so a client would have to type-check the
    # field before rendering it. Now the message is always a string and field
    # errors always live under details.
    assert isinstance(body["error"]["message"], str)
    assert isinstance(body["error"]["details"], list)


async def test_validation_details_name_the_field(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/shipments", json={"weight_kg": 90})
    fields = {item["field"] for item in response.json()["error"]["details"]}
    # A path the dashboard can match against a form field rather than the raw
    # ("body", "weight_kg") tuple.
    assert "weight_kg" in fields


async def test_the_request_id_matches_the_header(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/shipments/4242")
    # In the body as well as the header, because someone pasting a screenshot
    # of an error will include the body and not the network tab.
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


async def test_a_401_keeps_its_www_authenticate_header(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401
    # Rewriting the body must not drop the headers the exception carried.
    assert response.headers["www-authenticate"] == "Bearer"
