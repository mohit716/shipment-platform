from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.api.deps import CurrentUser
from app.core.security import verify_password
from app.core.tokens import create_access_token
from app.db.session import SessionDep
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/token",
    response_model=Token,
    summary="Exchange credentials for an access token",
    responses={401: {"description": "Those credentials are not valid."}},
)
async def login(
    # OAuth2PasswordRequestForm reads form-encoded username and password, not
    # JSON. That is what the spec requires, and it is why Swagger UI's Authorize
    # button works against this route without any extra wiring.
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> Token:
    result = await session.exec(select(User).where(User.email == form.username))
    user = result.first()

    # One message and one status for both "no such account" and "wrong
    # password". Distinguishing them turns the login route into a free way to
    # discover which email addresses are registered.
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if user is None or not verify_password(form.password, user.hashed_password):
        raise invalid

    # The subject is the user id, not the email. Ids do not change, so a token
    # stays valid if the account's address is later updated.
    return Token(access_token=create_access_token(str(user.id)))


@router.get(
    "/me",
    response_model=UserRead,
    summary="Read the authenticated account",
    responses={401: {"description": "Missing, expired or invalid token."}},
)
async def read_me(current_user: CurrentUser) -> User:
    # No session, no query, no path parameter. The dependency has already
    # turned the Authorization header into a row, which is the whole point of
    # putting that work behind a dependency rather than in each handler.
    return current_user
