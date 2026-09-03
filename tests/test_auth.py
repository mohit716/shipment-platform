import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

CREDENTIALS = {
    "email": "ada@example.com",
    "full_name": "Ada Lovelace",
    "password": "correct-horse",
}


async def register(client: AsyncClient, **overrides: str) -> dict:
    response = await client.post("/users", json={**CREDENTIALS, **overrides})
    return response.json()


async def login(
    client: AsyncClient, email: str = CREDENTIALS["email"], password: str = "correct-horse"
):
    # Form encoded, not JSON: that is what OAuth2's password flow specifies.
    return await client.post(
        "/auth/token", data={"username": email, "password": password}
    )


async def test_valid_credentials_return_a_bearer_token(client: AsyncClient) -> None:
    await register(client)
    response = await login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2


async def test_the_token_identifies_the_user_by_id(client: AsyncClient) -> None:
    from app.core.tokens import read_access_token

    user = await register(client)
    token = (await login(client)).json()["access_token"]

    # The subject is the id, not the email, so the token survives an address
    # change.
    assert read_access_token(token) == str(user["id"])


async def test_a_wrong_password_is_rejected(client: AsyncClient) -> None:
    await register(client)
    response = await login(client, password="wrong-horse")
    assert response.status_code == 401


async def test_an_unknown_email_is_rejected_identically(client: AsyncClient) -> None:
    await register(client)
    unknown = await login(client, email="nobody@example.com")
    wrong_password = await login(client, password="wrong-horse")

    # Same status and same message. Any difference would let an attacker
    # enumerate which addresses are registered.
    assert unknown.status_code == wrong_password.status_code == 401
    assert (
        unknown.json()["error"]["message"]
        == wrong_password.json()["error"]["message"]
    )


async def test_a_failed_login_advertises_the_scheme(client: AsyncClient) -> None:
    response = await login(client, email="nobody@example.com")
    assert response.headers["www-authenticate"] == "Bearer"


async def auth_header(client: AsyncClient) -> dict[str, str]:
    token = (await login(client)).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_me_returns_the_token_holder(client: AsyncClient) -> None:
    user = await register(client)
    response = await client.get("/auth/me", headers=await auth_header(client))

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


async def test_me_without_a_token_is_401(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_a_garbage_token_is_401_not_500(client: AsyncClient) -> None:
    response = await client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401


async def test_a_non_numeric_subject_is_401(client: AsyncClient) -> None:
    from app.core.tokens import create_access_token

    token = create_access_token("ada@example.com")
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_a_token_for_a_deleted_account_is_401(client: AsyncClient) -> None:
    from app.core.tokens import create_access_token

    # A valid signature only proves the token was issued, not that the account
    # still exists, which is why the dependency looks the row up.
    token = create_access_token("4242")
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_an_expired_token_is_401(client: AsyncClient) -> None:
    from app.core.tokens import create_access_token

    user = await register(client)
    token = create_access_token(str(user["id"]), expires_minutes=-1)
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_json_is_not_accepted_for_login(client: AsyncClient) -> None:
    await register(client)
    response = await client.post(
        "/auth/token",
        json={"username": CREDENTIALS["email"], "password": "correct-horse"},
    )
    assert response.status_code == 422
