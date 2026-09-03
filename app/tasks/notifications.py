import logging

from app.services.notifications import Notification, build_notifier
from app.worker import celery_app

logger = logging.getLogger("fleetline.tasks")


@celery_app.task(name="notifications.send")
def send_notification(payload: dict) -> None:
    """Deliver one notification from the queue.

    The argument is a plain dict rather than a Notification, because everything
    crossing the broker has to survive JSON. Reconstructing the dataclass here
    keeps the type where the work happens without asking Celery to understand
    it.

    build_notifier rather than the get_notifier dependency: the worker has no
    request and no dependency injection, so it builds the channel itself from
    the same settings the API reads.
    """
    notification = Notification(**payload)
    build_notifier().send(notification)
    logger.info(
        "delivered %s to %s", notification.channel, notification.recipient
    )
