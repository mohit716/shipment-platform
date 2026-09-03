from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.schemas.shipment import ShipmentStatus


class Shipment(SQLModel, table=True):
    """The shipments table.

    table=True is what separates a stored row from a plain schema: without it
    SQLModel behaves exactly like a Pydantic model and no table is created.
    """

    __tablename__ = "shipments"

    # None until the row is inserted, at which point the database assigns it.
    id: int | None = Field(default=None, primary_key=True)

    content: str = Field(max_length=120)
    weight_kg: float
    destination: int

    # index=True because shipments are listed and filtered by status constantly,
    # which is exactly the access pattern an index exists to serve.
    status: ShipmentStatus = Field(default=ShipmentStatus.placed, index=True)

    # default_factory, not default: passing datetime.now(...) directly would
    # evaluate once at import and stamp every row with the same time.
    #
    # sa_column forces TIMESTAMP WITH TIME ZONE. The inferred type is timezone
    # naive, and asyncpg refuses to write an aware datetime into a naive column.
    # SQLite accepted it silently, so this only surfaced on PostgreSQL.
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
