from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.shipment import Shipment


class ShipmentWarehouseLink(SQLModel, table=True):
    """The association table joining shipments to the warehouses they pass through.

    It holds nothing but the two foreign keys, and both together form the primary
    key, so the same warehouse cannot be added to a shipment twice. Adding a
    column here, such as an arrival time, would turn this into an association
    object and the relationship would have to be navigated through it rather than
    with link_model.
    """

    __tablename__ = "shipment_warehouse_links"

    shipment_id: int | None = Field(
        default=None,
        foreign_key="shipments.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    warehouse_id: int | None = Field(
        default=None,
        foreign_key="warehouses.id",
        primary_key=True,
        ondelete="CASCADE",
    )


class Warehouse(SQLModel, table=True):
    """A depot or sorting hub a shipment can be routed through."""

    __tablename__ = "warehouses"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=8, unique=True, index=True)
    name: str = Field(max_length=120)
    city: str = Field(max_length=80)

    # The other side of the same relationship declared on Shipment.stops.
    shipments: list["Shipment"] = Relationship(
        back_populates="stops",
        link_model=ShipmentWarehouseLink,
    )
