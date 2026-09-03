import pytest
from httpx import AsyncClient

from app.core.tokens import TokenPurpose, create_token
from app.services.notifications import MemoryNotifier

pytestmark = pytest.mark.anyio

CREDENTIALS = {
    "email": "ada@example.com",
    "full_name": "Ada Lovelace",
    "password": "correct-horse",
}


def reset_link_token(outbox: MemoryNotifier) -> str:
    reset = [m for m in outbox.sent if "Reset" in m.subject][-1]
    return reset.body.split("reset?token=")[1].split()[0]


async def login(client: AsyncClient, password: str):
    return await client.post(
        "/auth/token", data={"username": CREDENTIALS["email"], "password": password}
    )


async def test_requesting_a_reset_emails_a_link(
    client: AsyncClient, outbox: MemoryNotifier
) -> None:
    await client.post("/users", json=CREDENTIALS)
    response = await client.post(
        "/auth/forgot-password", json={"email": CREDENTIALS["email"]}
    )

    assert response.status_code == 202
    assert "/reset?token=" in outbox.sent[-1].body


async def test_an_unknown_address_answers_identically(
    client: AsyncClient, outbox: MemoryNotifier
) -> None:
    known = await client.post(
        "/auth/forgot-password", json={"email": CREDENTIALS["email"]}
    )
    unknown = await client.post(
        "/auth/forgot-password", json={"email": "nobody@example.com"}
    )

    # Identical, otherwise the route becomes a way to test whether a given
    # person has an account here.
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert outbox.sent == []


async def test_the_link_sets_a_new_password(
    client: AsyncClient, outbox: MemoryNotifier
) -> None:
    await client.post("/users", json=CREDENTIALS)
    await client.post("/auth/forgot-password", json={"email": CREDENTIALS["email"]})

    response = await client.post(
        "/auth/reset-password",
        json={"token": reset_link_token(outbox), "password": "a-brand-new-one"},
    )
    assert response.status_code == 204

    assert (await login(client, "a-brand-new-one")).status_code == 200
    assert (await login(client, "correct-horse")).status_code == 401


async def test_resetting_also_verifies_the_address(
    client: AsyncClient, outbox: MemoryNotifier
) -> None:
    await client.post("/users", json=CREDENTIALS)
    await client.post("/auth/forgot-password", json={"email": CREDENTIALS["email"]})
    await client.post(
        "/auth/reset-password",
        json={"token": reset_link_token(outbox), "password": "a-brand-new-one"},
    )

    token = (await login(client, "a-brand-new-one")).json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    # Following the link proves control of the mailbox, which is exactly what
    # verification proves, so leaving the account unverified makes no sense.
    assert me.json()["is_verified"] is True


async def test_a_verification_token_cannot_reset_a_password(
    client: AsyncClient,
) -> None:
    user = (await client.post("/users", json=CREDENTIALS)).json()
    token = create_token(str(user["id"]), TokenPurpose.verify_email)

    response = await client.post(
        "/auth/reset-password", json={"token": token, "password": "a-brand-new-one"}
    )
    assert response.status_code == 400


async def test_a_weak_new_password_is_rejected(
    client: AsyncClient, outbox: MemoryNotifier
) -> None:
    await client.post("/users", json=CREDENTIALS)
    await client.post("/auth/forgot-password", json={"email": CREDENTIALS["email"]})

    response = await client.post(
        "/auth/reset-password",
        json={"token": reset_link_token(outbox), "password": "short"},
    )
    # A reset that accepts weaker passwords than signup becomes the easiest way
    # to create a weak password.
    assert response.status_code == 422


async def test_an_expired_link_is_rejected(client: AsyncClient) -> None:
    user = (await client.post("/users", json=CREDENTIALS)).json()
    token = create_token(
        str(user["id"]), TokenPurpose.reset_password, expires_minutes=-1
    )
    response = await client.post(
        "/auth/reset-password", json={"token": token, "password": "a-brand-new-one"}
    )
    assert response.status_code == 400
