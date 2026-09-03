import logging

from app.services.notifications import Notification, build_notifier
from app.worker import celery_app

logger = logging.getLogger("fleetline.tasks")


@celery_app.task(
    name="notifications.send",
    bind=True,
    # Mail servers and SMS gateways fail transiently far more often than they
    # fail permanently, so the default is to try again rather than give up.
    autoretry_for=(Exception,),
    max_retries=5,
    # Exponential backoff: roughly 2, 4, 8, 16 and 32 seconds. Retrying
    # immediately would hammer a service that is already struggling, and five
    # attempts spread over a minute is the difference between riding out a
    # blip and amplifying an outage.
    retry_backoff=2,
    retry_backoff_max=60,
    # Without jitter every worker that failed at the same moment retries at the
    # same moment, and the recovering service is hit by a synchronised wave.
    retry_jitter=True,
)
def send_notification(self, payload: dict) -> None:
    """Deliver one notification from the queue, retrying transient failures.

    The argument is a plain dict rather than a Notification, because everything
    crossing the broker has to survive JSON. Reconstructing the dataclass here
    keeps the type where the work happens without asking Celery to understand
    it.

    build_notifier rather than the get_notifier dependency: the worker has no
    request and no dependency injection, so it builds the channel itself from
    the same settings the API reads.
    """
    notification = Notification(**payload)
    try:
        build_notifier().send(notification)
    except Exception:
        # Logged with the attempt number so a permanent failure is
        # distinguishable from a blip in the worker's output.
        logger.warning(
            "delivery to %s failed, attempt %s of %s",
            notification.recipient,
            self.request.retries + 1,
            self.max_retries,
        )
        raise

    logger.info("delivered %s to %s", notification.channel, notification.recipient)
