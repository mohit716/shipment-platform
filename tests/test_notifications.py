import pytest
from httpx import AsyncClient

from app.services.notifications import MemoryNotifier

pytestmark = pytest.mark.anyio

BOOKING = {"content": "ceramic dinnerware", "weight_kg": 2.4, "destination": 11001}


def confirmations(outbox: MemoryNotifier) -> list:
    """Only the booking confirmations.

    The outbox also holds the verification email that registration sends, so
    counting everything would make these tests fail whenever an unrelated
    message is added.
    """
    return [message for message in outbox.sent if "booking" in message.subject]


async def test_booking_sends_a_confirmation(
    auth_client: AsyncClient, outbox: MemoryNotifier
) -> None:
    created = (await auth_client.post("/shipments", json=BOOKING)).json()

    assert len(confirmations(outbox)) == 1
    message = confirmations(outbox)[0]
    assert message.channel == "email"
    assert message.recipient == "ada@example.com"
    assert str(created["id"]) in message.subject


async def test_a_rejected_booking_sends_nothing(
    auth_client: AsyncClient, outbox: MemoryNotifier
) -> None:
    # The task is queued after the commit, so a booking that never validates
    # cannot produce a confirmation for a shipment that does not exist.
    response = await auth_client.post(
        "/shipments", json={**BOOKING, "weight_kg": 90}
    )
    assert response.status_code == 422
    assert confirmations(outbox) == []


async def test_the_confirmation_names_the_customer_and_destination(
    auth_client: AsyncClient, outbox: MemoryNotifier
) -> None:
    await auth_client.post("/shipments", json=BOOKING)
    body = confirmations(outbox)[0].body
    assert "Ada Lovelace" in body
    assert "11001" in body
