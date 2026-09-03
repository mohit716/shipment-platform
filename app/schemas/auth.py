from pydantic import BaseModel


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
