from pydantic import BaseModel


class Shipment(BaseModel):
    """A shipment as it travels over the wire.

    Declaring the fields with types is enough for Pydantic to parse, validate and
    serialise them. A body of {"weight_kg": "heavy"} is now rejected with 422
    instead of being stored.
    """

    content: str
    weight_kg: float
    destination: int
    status: str
