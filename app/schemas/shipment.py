from enum import Enum

from pydantic import BaseModel, Field


class ShipmentStatus(str, Enum):
    """The states a shipment moves through, in order.

    Inheriting from str as well as Enum means members serialise as plain strings
    in JSON while still being a closed set the API refuses to deviate from.
    """

    placed = "placed"
    picked_up = "picked_up"
    in_transit = "in_transit"
    at_warehouse = "at_warehouse"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
    exception = "exception"


class Shipment(BaseModel):
    """A shipment as it travels over the wire.

    Field carries the business rules: a carrier that cannot lift more than 25 kg
    and a destination that must be a five digit postcode are facts about the
    domain, and stating them here means no handler has to re-check them.
    """

    content: str = Field(
        min_length=3,
        max_length=120,
        description="What is inside the parcel.",
    )
    weight_kg: float = Field(
        gt=0,
        le=25,
        description="Billable weight. Anything above 25 kg is freight, not parcel.",
    )
    destination: int = Field(
        ge=10000,
        le=99999,
        description="Five digit destination postcode.",
    )
    status: ShipmentStatus = Field(
        default=ShipmentStatus.placed,
        description="Current lifecycle state.",
    )
