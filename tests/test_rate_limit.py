import time

import pytest
from httpx import AsyncClient

from app.core.ratelimit import SlidingWindowLimiter, login_limiter

pytestmark = pytest.mark.anyio

CREDENTIALS = {
    "email": "ada@example.com",
    "full_name": "Ada Lovelace",
    "password": "correct-horse",
}


async def attempt(client: AsyncClient, password: str = "wrong-horse"):
    return await client.post(
        "/auth/token", data={"username": CREDENTIALS["email"], "password": password}
    )


async def test_repeated_failures_are_eventually_refused(client: AsyncClient) -> None:
    await client.post("/users", json=CREDENTIALS)

    for _ in range(login_limiter.limit):
        assert (await attempt(client)).status_code == 401

    # Guessing is cheap for the attacker and expensive here: every attempt
    # costs a bcrypt hash.
    assert (await attempt(client)).status_code == 429


async def test_the_refusal_says_when_to_come_back(client: AsyncClient) -> None:
    for _ in range(login_limiter.limit + 1):
        response = await attempt(client)

    assert int(response.headers["retry-after"]) > 0


async def test_the_limit_counts_successes_too(client: AsyncClient) -> None:
    await client.post("/users", json=CREDENTIALS)

    for _ in range(login_limiter.limit):
        assert (await attempt(client, "correct-horse")).status_code == 200

    # Counting only failures would let an attacker reset the window with one
    # valid login against any account they already control.
    assert (await attempt(client, "correct-horse")).status_code == 429


async def test_password_reset_requests_share_the_limit(client: AsyncClient) -> None:
    for _ in range(login_limiter.limit):
        await client.post("/auth/forgot-password", json={"email": "a@example.com"})

    response = await client.post(
        "/auth/forgot-password", json={"email": "a@example.com"}
    )
    # Otherwise the route is a free way to send mail to any address repeatedly.
    assert response.status_code == 429


def test_the_window_slides_rather_than_resetting() -> None:
    limiter = SlidingWindowLimiter(limit=2, window_seconds=1)

    assert limiter.check("ada") is True
    assert limiter.check("ada") is True
    assert limiter.check("ada") is False

    time.sleep(1.1)
    # With fixed buckets a caller could spend the whole allowance either side
    # of a boundary and get double the limit in a moment.
    assert limiter.check("ada") is True


def test_callers_are_counted_separately() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)

    assert limiter.check("ada") is True
    assert limiter.check("ada") is False
    # One noisy address must not lock everyone else out.
    assert limiter.check("grace") is True
