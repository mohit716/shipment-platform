import pytest
from httpx import AsyncClient

from app.core.security import hash_password, verify_password

pytestmark = pytest.mark.anyio


def test_a_hash_does_not_contain_the_password() -> None:
    hashed = hash_password("correct-horse")
    assert "correct-horse" not in hashed
    assert hashed.startswith("$2b$")


def test_the_same_password_hashes_differently_each_time() -> None:
    # A fresh random salt per call is why two users with the same password do
    # not share a hash, and why a stolen hash cannot be looked up in a table.
    assert hash_password("correct-horse") != hash_password("correct-horse")


def test_verification_accepts_the_right_password() -> None:
    assert verify_password("correct-horse", hash_password("correct-horse"))


def test_verification_rejects_the_wrong_password() -> None:
    assert not verify_password("wrong-horse", hash_password("correct-horse"))


def test_a_corrupt_hash_reads_as_a_failed_login() -> None:
    # Never a 500 on the login route because of a bad row.
    assert not verify_password("correct-horse", "not-a-bcrypt-hash")


async def test_registration_never_echoes_the_password(client: AsyncClient) -> None:
    response = await client.post(
        "/users",
        json={
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "password": "correct-horse",
        },
    )
    body = response.json()
    assert "password" not in body
    assert "hashed_password" not in body


async def test_a_short_password_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/users",
        json={"email": "ada@example.com", "full_name": "Ada", "password": "short"},
    )
    assert response.status_code == 422


async def test_a_password_beyond_bcrypts_limit_is_rejected(
    client: AsyncClient,
) -> None:
    # bcrypt silently ignores bytes past 72, so accepting a longer one would
    # misrepresent how much of it is checked.
    response = await client.post(
        "/users",
        json={
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "password": "a" * 73,
        },
    )
    assert response.status_code == 422
