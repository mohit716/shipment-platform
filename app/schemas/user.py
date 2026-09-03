from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(UserBase):
    id: int
    created_at: datetime
