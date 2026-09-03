from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """What an account is allowed to do.

    Two roles, not a permission matrix. Roles answer "who are you" and the
    dependencies answer "may you do this", which is enough until the answers
    stop lining up. Inheriting from str keeps the JSON representation plain.
    """

    customer = "customer"
    staff = "staff"


class UserBase(BaseModel):
    # EmailStr does real syntactic validation rather than a hand-rolled regex,
    # so "not-an-email" is rejected at the edge with a 422.
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)


class UserCreate(UserBase):
    # Capped at bcrypt's 72 byte limit. Past that the algorithm ignores the
    # remainder, so accepting a longer password would be a lie about how much
    # of it is actually checked.
    password: str = Field(min_length=8, max_length=72)

    # Unknown keys are rejected rather than dropped. Pydantic would already
    # ignore a role sent here, but silently: the caller would get a 201 and
    # believe it had been granted. A 422 says plainly that it was not.
    model_config = {"extra": "forbid"}


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(UserBase):
    id: int
    created_at: datetime
    # Readable but not writable: UserCreate has no role field, so registration
    # cannot ask for one.
    role: UserRole
