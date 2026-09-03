from datetime import datetime, timezone

from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.schemas.shipment import ShipmentStatus

if TYPE_CHECKING:
    from app.models.package import Package
    from app.models.user import User


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

    # A foreign key is enforced by the database: a shipment cannot reference a
    # customer that does not exist, and the customer cannot be deleted while
    # shipments still point at them. Indexed because "every shipment for this
    # customer" is the query the dashboard runs constantly.
    customer_id: int = Field(foreign_key="users.id", index=True)

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

    # back_populates is what pairs the two sides. Setting shipment.customer also
    # updates that user's shipments list in the same session, because both names
    # describe one relationship rather than two independent ones.
    customer: "User" = Relationship(back_populates="shipments")

    # cascade delete-orphan means deleting a shipment deletes its packages, and
    # removing a package from this list deletes that row rather than leaving it
    # parentless.
    packages: list["Package"] = Relationship(
        back_populates="shipment",
        cascade_delete=True,
    )
