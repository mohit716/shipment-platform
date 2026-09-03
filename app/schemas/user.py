from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    # EmailStr does real syntactic validation rather than a hand-rolled regex,
    # so "not-an-email" is rejected at the edge with a 422.
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int
    created_at: datetime
