import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

DASHBOARD = "http://localhost:5173"


async def test_the_dashboard_origin_is_allowed(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": DASHBOARD})
    assert response.headers["access-control-allow-origin"] == DASHBOARD


async def test_an_unknown_origin_gets_no_permission(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": "http://evil.example"})
    # The request still succeeds; it is the browser that refuses to hand the
    # body to the calling script when this header is missing.
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_the_preflight_permits_the_authorization_header(
    client: AsyncClient,
) -> None:
    response = await client.options(
        "/shipments",
        headers={
            "Origin": DASHBOARD,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    # Authorization is not on the browser's safelist, so omitting it here would
    # break every authenticated request from the dashboard.
    assert "authorization" in allowed


async def test_credentials_are_permitted(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": DASHBOARD})
    assert response.headers["access-control-allow-credentials"] == "true"
