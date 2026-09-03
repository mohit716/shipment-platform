from pydantic import BaseModel, Field, field_validator


class WarehouseBase(BaseModel):
    code: str = Field(min_length=3, max_length=8, description="Short depot code.")
    name: str = Field(min_length=3, max_length=120)
    city: str = Field(min_length=2, max_length=80)

    @field_validator("code")
    @classmethod
    def normalise_code(cls, value: str) -> str:
        """Depot codes are upper case by convention, so store them that way.

        Normalising here means "lds1" and "LDS1" cannot both be registered as
        separate warehouses.
        """
        return value.strip().upper()


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseRead(WarehouseBase):
    id: int
