from datetime import datetime, timezone

from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.schemas.user import UserRole

if TYPE_CHECKING:
    # Import only for type checkers. At runtime this would be a circular import,
    # since shipment.py imports this module too. SQLModel resolves the string
    # annotation lazily, so the real class is never needed here.
    from app.models.shipment import Shipment


class User(SQLModel, table=True):
    """A customer who books shipments and can log in."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)

    # unique is a database constraint, so two rows with the same address are
    # impossible even if two requests race. index makes the lookup by email fast,
    # which is what every login will do once auth exists.
    email: str = Field(max_length=255, unique=True, index=True)
    full_name: str = Field(max_length=120)

    # The hash, never the password. Nothing in the codebase reads this field
    # except verify_password, and no response schema exposes it.
    hashed_password: str = Field(max_length=128)

    # Not settable through the public registration endpoint. Everyone who signs
    # up is a customer; staff are promoted deliberately, because a role a client
    # can choose is not a permission boundary at all.
    role: UserRole = Field(default=UserRole.customer, index=True)

    # Proves the address reaches the person who claimed it. Registration is
    # still allowed without it; what it gates is decided per route.
    is_verified: bool = Field(default=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Not a column. Relationship is a Python-level view over the foreign key on
    # the other table, so user.shipments issues a query rather than reading a
    # stored value.
    shipments: list["Shipment"] = Relationship(back_populates="customer")
