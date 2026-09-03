"""HTTP-level builders used by the tests.

Factories go through the API rather than inserting rows, so they exercise the
same validation, hashing and ownership rules as a real caller. A test that
builds a User() and session.add()s it would silently skip all of that, and a
bug in registration would only show up in the registration tests.
"""

from httpx import AsyncClient

PASSWORD = "correct-horse"

BOOKING = {
    "content": "ceramic dinnerware",
    "weight_kg": 2.4,
    "destination": 11001,
}

DEPOT = {"code": "LDS1", "name": "Leeds Central Depot", "city": "Leeds"}


async def register(
    client: AsyncClient,
    *,
    email: str = "ada@example.com",
    full_name: str = "Ada Lovelace",
    password: str = PASSWORD,
) -> dict:
    """Create an account and return the API's representation of it."""
    response = await client.post(
        "/users",
        json={"email": email, "full_name": full_name, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login(
    client: AsyncClient,
    *,
    email: str = "ada@example.com",
    password: str = PASSWORD,
) -> str:
    """Exchange credentials for an access token."""
    response = await client.post(
        "/auth/token", data={"username": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def bearer(
    client: AsyncClient,
    *,
    email: str = "ada@example.com",
    full_name: str = "Ada Lovelace",
    password: str = PASSWORD,
) -> dict[str, str]:
    """Register, log in, and return an Authorization header.

    Used when a test needs a second caller without disturbing the client
    fixture's own header.
    """
    await register(client, email=email, full_name=full_name, password=password)
    token = await login(client, email=email, password=password)
    return {"Authorization": f"Bearer {token}"}


async def book(client: AsyncClient, **overrides: object) -> dict:
    """Book a shipment as whoever the client is currently authenticated as."""
    response = await client.post("/shipments", json={**BOOKING, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


async def depot(client: AsyncClient, **overrides: object) -> dict:
    """Register a warehouse. The caller must be staff."""
    response = await client.post("/warehouses", json={**DEPOT, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


async def tag(client: AsyncClient, name: str = "fragile", **overrides: object) -> dict:
    """Define a handling label. The caller must be staff."""
    response = await client.post(
        "/tags", json={"name": name, "requires_signature": False, **overrides}
    )
    assert response.status_code == 201, response.text
    return response.json()
