from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    """The OAuth2 token response.

    The field names are fixed by the spec, including the lower case "bearer"
    token type. Clients such as Swagger UI's Authorize button read exactly
    these keys, so renaming them to something tidier would break them.
    """

    access_token: str
    token_type: str = "bearer"


class VerificationRequest(BaseModel):
    """The token lifted out of a verification link."""

    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    # Same rules as registration, because a reset that accepts a weaker password
    # than signup would quietly become the easiest way in.
    password: str = Field(min_length=8, max_length=72)
