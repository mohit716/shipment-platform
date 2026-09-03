from enum import Enum

from pydantic import BaseModel


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

    Declaring the fields with types is enough for Pydantic to parse, validate and
    serialise them. A body of {"weight_kg": "heavy"} is now rejected with 422
    instead of being stored.
    """

    content: str
    weight_kg: float
    destination: int
    status: ShipmentStatus
