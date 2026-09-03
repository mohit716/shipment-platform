import pytest
from httpx import AsyncClient

from app.core.tokens import TokenPurpose, create_access_token, create_token
from app.services.notifications import MemoryNotifier

pytestmark = pytest.mark.anyio

CREDENTIALS = {
    "email": "ada@example.com",
    "full_name": "Ada Lovelace",
    "password": "correct-horse",
}


def token_from(outbox: MemoryNotifier) -> str:
    """Pull the token out of the emailed link, as a real user's browser would."""
    return outbox.sent[-1].body.split("token=")[1].strip()


async def test_registration_starts_unverified(client: AsyncClient) -> None:
    response = await client.post("/users", json=CREDENTIALS)
    assert response.json()["is_verified"] is False


async def test_registration_emails_a_verification_link(
    client: AsyncClient, outbox: MemoryNotifier
) -> None:
    await client.post("/users", json=CREDENTIALS)
    assert outbox.sent[-1].recipient == "ada@example.com"
    assert "/verify?token=" in outbox.sent[-1].body


async def test_the_emailed_token_verifies_the_account(
    client: AsyncClient, outbox: MemoryNotifier
) -> None:
    await client.post("/users", json=CREDENTIALS)
    response = await client.post("/auth/verify", json={"token": token_from(outbox)})

    assert response.status_code == 200
    assert response.json()["is_verified"] is True


async def test_verifying_twice_is_not_an_error(
    client: AsyncClient, outbox: MemoryNotifier
) -> None:
    await client.post("/users", json=CREDENTIALS)
    token = token_from(outbox)
    await client.post("/auth/verify", json={"token": token})

    # Mail clients prefetch links, so the second visit is routine.
    assert (
        await client.post("/auth/verify", json={"token": token})
    ).status_code == 200


async def test_an_access_token_cannot_verify_an_account(
    client: AsyncClient,
) -> None:
    user = (await client.post("/users", json=CREDENTIALS)).json()
    response = await client.post(
        "/auth/verify", json={"token": create_access_token(str(user["id"]))}
    )
    # Same secret, same signature, same subject: only the purpose claim stops
    # one kind of token being spent as another.
    assert response.status_code == 400


async def test_a_verification_token_cannot_call_the_api(
    client: AsyncClient,
) -> None:
    user = (await client.post("/users", json=CREDENTIALS)).json()
    token = create_token(str(user["id"]), TokenPurpose.verify_email)

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    # The direction that actually matters: verification links travel in
    # plaintext email and are routinely logged by mail servers.
    assert response.status_code == 401


async def test_an_expired_link_is_rejected(client: AsyncClient) -> None:
    user = (await client.post("/users", json=CREDENTIALS)).json()
    token = create_token(
        str(user["id"]), TokenPurpose.verify_email, expires_minutes=-1
    )
    response = await client.post("/auth/verify", json={"token": token})
    assert response.status_code == 400


async def test_a_garbage_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/auth/verify", json={"token": "not-a-jwt"})
    assert response.status_code == 400
