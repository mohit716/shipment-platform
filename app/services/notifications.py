import logging
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger("fleetline.notifications")


@dataclass(frozen=True)
class Notification:
    """One message, independent of how it will be delivered.

    Kept as data rather than being sent inline so the same object can be
    logged, queued or asserted on in a test. Phase 10 hands exactly this to a
    Celery worker.
    """

    channel: str
    recipient: str
    subject: str
    body: str
    sent_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), compare=False
    )


class Notifier(Protocol):
    """What a delivery channel must do.

    A Protocol rather than a base class: nothing has to inherit from it, so a
    test double is any object with a send method. This is what makes the
    console, SMTP and in-memory backends interchangeable.
    """

    def send(self, notification: Notification) -> None: ...


class ConsoleNotifier:
    """Writes to the log instead of sending anything.

    The default in development. Wiring a real SMTP server just to see whether a
    booking confirmation fires is a poor trade, and a shipping demo that emails
    strangers is worse.
    """

    def send(self, notification: Notification) -> None:
        logger.info(
            "[%s] to=%s subject=%s\n%s",
            notification.channel,
            notification.recipient,
            notification.subject,
            notification.body,
        )


class SMTPNotifier:
    """Sends real email through an SMTP relay."""

    def send(self, notification: Notification) -> None:
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = notification.recipient
        message["Subject"] = notification.subject
        message.set_content(notification.body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_username:
                server.starttls()
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)


class MemoryNotifier:
    """Keeps everything in a list so tests can assert on it.

    Lives here rather than in the test suite because it is the reference
    implementation of the protocol, and keeping it beside the others means a
    change to Notification cannot break it silently.
    """

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def send(self, notification: Notification) -> None:
        self.sent.append(notification)


def get_notifier() -> Notifier:
    """The channel this deployment uses, chosen by configuration.

    A dependency rather than a module-level singleton, so a test can override
    it the same way it overrides the database session.
    """
    if settings.email_backend == "smtp":
        return SMTPNotifier()
    return ConsoleNotifier()
