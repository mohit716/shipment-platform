from pydantic import BaseModel, Field


class PackageBase(BaseModel):
    description: str = Field(min_length=2, max_length=120)
    weight_kg: float = Field(gt=0, le=25)
    length_cm: float = Field(gt=0, le=200)
    width_cm: float = Field(gt=0, le=200)
    height_cm: float = Field(gt=0, le=200)


class PackageCreate(PackageBase):
    """A box supplied as part of a booking. shipment_id comes from the parent."""


class PackageRead(PackageBase):
    id: int
    shipment_id: int
    # Computed on the model rather than stored, so it can never disagree with
    # the dimensions it is derived from.
    volumetric_weight_kg: float
