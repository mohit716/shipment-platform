from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.shipment import ShipmentStatus


class TrackingEventCreate(BaseModel):
    """A scan recorded by a depot, carrier or courier."""

    status: ShipmentStatus
    location: str = Field(min_length=2, max_length=120)
    note: str | None = Field(default=None, max_length=240)


class TrackingEventRead(TrackingEventCreate):
    id: int
    shipment_id: int
    recorded_at: datetime
