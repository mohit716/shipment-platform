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

    def as_payload(self) -> dict[str, str]:
        """The message in a form that survives the broker.

        Everything crossing a queue has to be JSON, so the timestamp becomes a
        string and is rebuilt on the other side. Serialising by hand rather than
        registering a custom encoder keeps the contract visible: whatever is in
        this dict is what the worker will see.
        """
        return {
            "channel": self.channel,
            "recipient": self.recipient,
            "subject": self.subject,
            "body": self.body,
        }


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


class SMSNotifier:
    """Stands in for a gateway such as Twilio.

    Not wired to a real provider: every SMS gateway needs an account, a paid
    number and a verified sender, none of which teaches anything the interface
    does not already show. What matters is that the channel plugs in without a
    single caller changing.
    """

    def send(self, notification: Notification) -> None:
        logger.info(
            "[sms] to=%s %s",
            notification.recipient,
            # Real gateways bill per 160 character segment, so the body is
            # truncated here rather than surprising anyone with the bill.
            notification.body[:160],
        )


class CompositeNotifier:
    """Fans one message out to several channels.

    Callers still see a single Notifier, so adding SMS alongside email is a
    configuration change rather than an edit to every place that sends.
    """

    def __init__(self, *notifiers: "Notifier") -> None:
        self.notifiers = notifiers

    def send(self, notification: Notification) -> None:
        for notifier in self.notifiers:
            # One failing channel must not silence the others. An email that
            # arrives is better than neither, and a failed SMS is not a reason
            # to fail the request that triggered it.
            try:
                notifier.send(notification)
            except Exception:
                logger.exception("channel %r failed", notifier)


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


class QueueNotifier:
    """Hands the message to a worker instead of delivering it.

    The API's send becomes an enqueue that returns in microseconds. Delivery,
    including anything slow or flaky about it, happens in another process.
    """

    def send(self, notification: Notification) -> None:
        # Imported inside the method: app.tasks imports the notification
        # services, so importing it at module scope would be circular.
        from app.tasks.notifications import send_notification

        send_notification.delay(notification.as_payload())


def build_notifier() -> Notifier:
    """The delivery channel this deployment uses, chosen by configuration.

    Used by the worker, which actually delivers. The API goes through
    get_notifier instead and normally only enqueues.
    """
    email: Notifier = (
        SMTPNotifier() if settings.email_backend == "smtp" else ConsoleNotifier()
    )
    if not settings.sms_enabled:
        return email
    return CompositeNotifier(email, SMSNotifier())


def get_notifier() -> Notifier:
    """What the API sends through.

    A dependency rather than a module-level singleton, so a test can override
    it the same way it overrides the database session. With a worker running
    this only enqueues; with celery_enabled off it delivers inline, so the
    project still runs with nothing but Python and a database.
    """
    if settings.celery_enabled:
        return QueueNotifier()
    return build_notifier()
