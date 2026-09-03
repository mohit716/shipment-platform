import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class Carrier:
    name: str
    base_fee: float
    per_kg: float
    # Stands in for the network round trip to that carrier's pricing API.
    latency_seconds: float


CARRIERS = (
    Carrier("Northwind Freight", base_fee=4.50, per_kg=1.20, latency_seconds=0.35),
    Carrier("Cobalt Express", base_fee=7.00, per_kg=0.80, latency_seconds=0.60),
    Carrier("Harbour Logistics", base_fee=3.20, per_kg=1.65, latency_seconds=0.45),
)


@dataclass(frozen=True)
class RateQuote:
    carrier: str
    price: float
    latency_seconds: float


async def quote_carrier(carrier: Carrier, weight_kg: float) -> RateQuote:
    """Ask one carrier what it would charge.

    asyncio.sleep yields control back to the event loop rather than blocking it.
    time.sleep here would freeze the entire application, which is the single
    most common way async code is accidentally made worse than sync code.
    """
    await asyncio.sleep(carrier.latency_seconds)
    price = round(carrier.base_fee + weight_kg * carrier.per_kg, 2)
    return RateQuote(
        carrier=carrier.name,
        price=price,
        latency_seconds=carrier.latency_seconds,
    )


async def quote_all_carriers(weight_kg: float) -> list[RateQuote]:
    """Ask every carrier at once.

    Awaiting the calls one after another would take the sum of their latencies,
    1.4 seconds. gather starts them together, so the wait is the slowest single
    call, 0.6 seconds. Nothing here is parallel in the CPU sense; the requests
    are simply all in flight while the loop waits.
    """
    quotes = await asyncio.gather(
        *(quote_carrier(carrier, weight_kg) for carrier in CARRIERS)
    )
    return sorted(quotes, key=lambda quote: quote.price)
