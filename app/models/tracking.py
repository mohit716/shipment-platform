from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.schemas.shipment import ShipmentStatus

if TYPE_CHECKING:
    from app.models.shipment import Shipment


class TrackingEvent(SQLModel, table=True):
    """One entry in a shipment's journey.

    Append only. The shipment's status column is the latest position; this table
    is how it got there, which is what a customer actually wants to see and what
    makes a dispute answerable.
    """

    __tablename__ = "tracking_events"

    id: int | None = Field(default=None, primary_key=True)

    shipment_id: int = Field(
        foreign_key="shipments.id",
        index=True,
        ondelete="CASCADE",
    )

    status: ShipmentStatus
    location: str = Field(max_length=120)
    note: str | None = Field(default=None, max_length=240)

    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )

    shipment: "Shipment" = Relationship(back_populates="tracking_events")
