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


class ShipmentBase(BaseModel):
    """Fields common to every representation of a shipment.

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


class ShipmentCreate(ShipmentBase):
    """What a client may send when booking. Note the absence of id."""

    status: ShipmentStatus = Field(
        default=ShipmentStatus.placed,
        description="Current lifecycle state.",
    )


class ShipmentUpdate(BaseModel):
    """A partial update, so every field is optional.

    None means the client did not mention the field, which is why handlers must
    use exclude_unset rather than treating None as a value to store.
    """

    content: str | None = Field(default=None, min_length=3, max_length=120)
    weight_kg: float | None = Field(default=None, gt=0, le=25)
    destination: int | None = Field(default=None, ge=10000, le=99999)
    status: ShipmentStatus | None = None


class ShipmentRead(ShipmentBase):
    """What the API returns. The server owns id, so it appears only here."""

    id: int
    status: ShipmentStatus
