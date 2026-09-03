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


def status_updates(outbox: MemoryNotifier) -> list:
    return [message for message in outbox.sent if "is now" in message.subject]


async def test_a_scan_notifies_the_customer(
    staff_client: AsyncClient, outbox: MemoryNotifier
) -> None:
    created = (await staff_client.post("/shipments", json=BOOKING)).json()
    await staff_client.post(
        f"/shipments/{created['id']}/tracking",
        json={"status": "picked_up", "location": "Leeds depot"},
    )

    assert len(status_updates(outbox)) == 1
    assert "picked_up" in status_updates(outbox)[0].subject


async def test_a_rescan_at_the_same_status_stays_quiet(
    staff_client: AsyncClient, outbox: MemoryNotifier
) -> None:
    created = (await staff_client.post("/shipments", json=BOOKING)).json()
    for location in ("Leeds depot", "Leeds outbound", "Leeds gate"):
        await staff_client.post(
            f"/shipments/{created['id']}/tracking",
            json={"status": "picked_up", "location": location},
        )

    # Three scans, one notification. Depots rescan parcels constantly, and a
    # customer texted on every barcode read stops reading them.
    assert len(status_updates(outbox)) == 1


async def test_the_customer_is_notified_not_the_staff_member(
    auth_client: AsyncClient, session_factory, outbox: MemoryNotifier
) -> None:
    from tests.conftest import login_as, promote_to_staff

    created = (await auth_client.post("/shipments", json=BOOKING)).json()
    staff = await login_as(auth_client, "depot@example.com", "Depot Operator")
    await promote_to_staff(session_factory, "depot@example.com")

    await auth_client.post(
        f"/shipments/{created['id']}/tracking",
        json={"status": "picked_up", "location": "Leeds depot"},
        headers=staff,
    )

    assert status_updates(outbox)[0].recipient == "ada@example.com"


def test_one_failing_channel_does_not_silence_the_others() -> None:
    from app.services.notifications import CompositeNotifier, Notification

    class Broken:
        def send(self, notification: Notification) -> None:
            raise RuntimeError("gateway down")

    working = MemoryNotifier()
    CompositeNotifier(Broken(), working).send(
        Notification(channel="email", recipient="a@b.c", subject="s", body="b")
    )

    # An email that arrives beats neither, and a dead SMS gateway is not a
    # reason to fail the request that triggered it.
    assert len(working.sent) == 1
