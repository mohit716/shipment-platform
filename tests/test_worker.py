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


def test_delivery_failures_propagate_so_celery_retries(monkeypatch) -> None:
    from app.tasks import notifications as task_module

    class Broken:
        def send(self, notification: Notification) -> None:
            raise RuntimeError("smtp unavailable")

    monkeypatch.setattr(task_module, "build_notifier", lambda: Broken())

    # Swallowing the exception here would look tidy and would silently turn
    # every failed delivery into a success as far as the queue is concerned.
    # autoretry_for only sees exceptions that escape the task body.
    try:
        task_module.send_notification(MESSAGE.as_payload())
    except RuntimeError:
        pass
    else:
        raise AssertionError("the task must not swallow delivery failures")


def test_the_retry_policy_is_bounded_and_backs_off() -> None:
    from app.tasks.notifications import send_notification

    # Unbounded retries turn a permanently bad address into a task that never
    # leaves the queue.
    assert send_notification.max_retries == 5
    assert send_notification.retry_backoff == 2
    assert send_notification.retry_jitter is True


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
