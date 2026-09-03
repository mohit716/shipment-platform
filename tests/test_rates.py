import time
from unittest.mock import AsyncMock

import pytest

from app.services.notifications import Notification, SMTPNotifier
from app.services.rates import CARRIERS, quote_all_carriers, quote_carrier

pytestmark = pytest.mark.anyio


async def test_carriers_are_asked_at_the_same_time(monkeypatch) -> None:
    """Concurrency is proven by when the sleeps start, not by waiting them out.

    Patching asyncio.sleep to record a timestamp and return immediately means
    the test does not spend 0.6 seconds sitting on a fake network, and still
    fails if quote_all_carriers awaits the carriers one after another: sequential
    starts would be spaced apart, concurrent starts cluster together.
    """
    started: list[float] = []

    async def mark_and_return(_seconds: float) -> None:
        started.append(time.perf_counter())

    monkeypatch.setattr("app.services.rates.asyncio.sleep", mark_and_return)

    await quote_all_carriers(2.0)

    assert len(started) == len(CARRIERS)
    assert max(started) - min(started) < 0.05


async def test_a_single_quote_uses_the_carrier_formula(monkeypatch) -> None:
    monkeypatch.setattr("app.services.rates.asyncio.sleep", AsyncMock())
    quote = await quote_carrier(CARRIERS[0], 2.0)
    assert quote.price == round(CARRIERS[0].base_fee + 2.0 * CARRIERS[0].per_kg, 2)


def test_smtp_can_be_replaced_without_a_mail_server(monkeypatch) -> None:
    """smtplib is patched at the import site, not globally.

    monkeypatch.setattr on app.services.notifications.smtplib.SMTP is what
    intercepts the call. Patching smtplib.SMTP on the stdlib module would miss
    a `from smtplib import SMTP` import, which is why the tests patch where
    the name is used.
    """
    sent = []

    class FakeSMTP:
        def __init__(self, host, port):
            self.host, self.port = host, port

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr("app.services.notifications.smtplib.SMTP", FakeSMTP)

    SMTPNotifier().send(
        Notification(
            channel="email",
            recipient="ada@example.com",
            subject="booking confirmed",
            body="ok",
        )
    )
    assert sent[0]["To"] == "ada@example.com"
    assert sent[0]["Subject"] == "booking confirmed"
