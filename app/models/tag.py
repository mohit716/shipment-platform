from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.shipment import Shipment


class ShipmentTagLink(SQLModel, table=True):
    """Joins shipments to their handling labels."""

    __tablename__ = "shipment_tag_links"

    shipment_id: int | None = Field(
        default=None,
        foreign_key="shipments.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    tag_id: int | None = Field(
        default=None,
        foreign_key="tags.id",
        primary_key=True,
        ondelete="CASCADE",
    )


class Tag(SQLModel, table=True):
    """A handling instruction such as Fragile, Perishable or Hazardous.

    Tags are a shared vocabulary rather than free text on the shipment, so the
    set stays closed, spelling stays consistent, and "every hazardous parcel in
    this depot" is a query rather than a substring search.
    """

    __tablename__ = "tags"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=40, unique=True, index=True)
    requires_signature: bool = Field(default=False)

    shipments: list["Shipment"] = Relationship(
        back_populates="tags",
        link_model=ShipmentTagLink,
    )
