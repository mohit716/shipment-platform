import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlmodel import Session, select

from app.core.config import settings
from app.models.shipment import Shipment
from app.schemas.shipment import ShipmentStatus
from app.services.notifications import Notification, build_notifier
from app.worker import celery_app

logger = logging.getLogger("fleetline.tasks")

# Stalled shipments are anything still sitting at placed after this long.
STALE_AFTER = timedelta(days=2)


def _sync_engine():
    """A synchronous engine for the worker.

    The API is async because it serves many concurrent requests. A worker task
    is one job on one thread, so async buys nothing and costs an event loop, an
    async session and the greenlet plumbing that goes with them. The driver
    prefix is swapped rather than a second URL being configured, so there is
    only ever one database address to get wrong.
    """
    url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg")
    return create_engine(url, pool_pre_ping=True)


@celery_app.task(name="maintenance.flag_stalled_shipments")
def flag_stalled_shipments() -> int:
    """Warn customers about shipments that were booked but never collected.

    Returns the number flagged, so the scheduled run leaves a number in the
    result backend rather than only a log line.
    """
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    notifier = build_notifier()
    flagged = 0

    with Session(_sync_engine()) as session:
        statement = select(Shipment).where(
            Shipment.status == ShipmentStatus.placed,
            Shipment.created_at < cutoff,
        )
        for shipment in session.exec(statement):
            notifier.send(
                Notification(
                    channel="email",
                    recipient=shipment.customer.email,
                    subject=f"Shipment {shipment.id} has not been collected",
                    body=(
                        f"Hello {shipment.customer.full_name},\n\n"
                        f"Shipment {shipment.id} was booked on "
                        f"{shipment.created_at:%d %B} and has not been "
                        f"collected yet. We are looking into it.\n"
                    ),
                )
            )
            flagged += 1

    logger.info("flagged %s stalled shipments", flagged)
    return flagged


celery_app.conf.beat_schedule = {
    "flag-stalled-shipments-hourly": {
        "task": "maintenance.flag_stalled_shipments",
        "schedule": 3600.0,
        # Beat is a separate process from the worker. It only publishes
        # messages on a timer; the worker still does the work, which is why one
        # beat and several workers is the normal shape.
    }
}
