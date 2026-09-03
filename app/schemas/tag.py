from pydantic import BaseModel, Field, field_validator


class TagBase(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    requires_signature: bool = False

    @field_validator("name")
    @classmethod
    def normalise_name(cls, value: str) -> str:
        """Lower case and collapse whitespace so the vocabulary stays closed.

        Without this, "Fragile", "fragile" and " Fragile " become three separate
        tags and the unique constraint never fires.
        """
        return " ".join(value.split()).lower()


class TagCreate(TagBase):
    pass


class TagRead(TagBase):
    id: int
