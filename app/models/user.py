from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """A customer who books shipments.

    Authentication arrives in phase 8; for now a user is just an identity a
    shipment can belong to.
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)

    # unique is a database constraint, so two rows with the same address are
    # impossible even if two requests race. index makes the lookup by email fast,
    # which is what every login will do once auth exists.
    email: str = Field(max_length=255, unique=True, index=True)
    full_name: str = Field(max_length=120)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
