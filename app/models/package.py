from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.shipment import Shipment


class Package(SQLModel, table=True):
    """One physical box within a shipment.

    A shipment of three boxes is one booking and one tracking number, but three
    rows here, each with its own dimensions and weight.
    """

    __tablename__ = "packages"

    id: int | None = Field(default=None, primary_key=True)

    # ondelete CASCADE is the database enforcing that a package cannot outlive
    # its shipment. The ORM cascade below covers objects already loaded in a
    # session; this covers everything else, including a manual DELETE in psql.
    shipment_id: int = Field(
        foreign_key="shipments.id",
        index=True,
        ondelete="CASCADE",
    )

    description: str = Field(max_length=120)
    weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float

    shipment: "Shipment" = Relationship(back_populates="packages")

    @property
    def volumetric_weight_kg(self) -> float:
        """Couriers bill the greater of actual and volumetric weight.

        The 5000 divisor is the industry standard for centimetres.
        """
        return round(self.length_cm * self.width_cm * self.height_cm / 5000, 2)
