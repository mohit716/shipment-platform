import json

from app.services.notifications import (
    MemoryNotifier,
    Notification,
    QueueNotifier,
)

MESSAGE = Notification(
    channel="email",
    recipient="ada@example.com",
    subject="Shipment 1 is now picked_up",
    body="Your parcel was scanned.",
)


def test_the_payload_survives_json() -> None:
    # Everything crossing the broker has to round-trip through JSON, and a
    # datetime does not, which is why sent_at is left out of the payload.
    payload = MESSAGE.as_payload()
    assert json.loads(json.dumps(payload)) == payload


def test_the_payload_rebuilds_the_notification() -> None:
    rebuilt = Notification(**MESSAGE.as_payload())
    # Equality ignores sent_at, which the worker stamps fresh on arrival.
    assert rebuilt == MESSAGE


def test_the_task_delivers_through_the_configured_channel(monkeypatch) -> None:
    from app.tasks import notifications as task_module

    delivered = MemoryNotifier()
    monkeypatch.setattr(task_module, "build_notifier", lambda: delivered)

    # Called directly rather than through .delay, so the test needs no broker
    # and no worker. What is being checked is the task body.
    task_module.send_notification(MESSAGE.as_payload())

    assert delivered.sent == [MESSAGE]


def test_the_api_enqueues_rather_than_delivering(monkeypatch) -> None:
    from app.tasks import notifications as task_module

    enqueued: list[dict] = []
    monkeypatch.setattr(
        task_module.send_notification, "delay", lambda payload: enqueued.append(payload)
    )

    QueueNotifier().send(MESSAGE)

    # The route returns as soon as the message is on the queue; nothing was
    # delivered in this process.
    assert enqueued == [MESSAGE.as_payload()]
