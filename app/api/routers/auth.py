from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.api.deps import CurrentUser, NotifierDep
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.tokens import (
    TokenError,
    TokenPurpose,
    create_access_token,
    create_token,
    read_token,
)
from app.db.session import SessionDep
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    Token,
    VerificationRequest,
)
from app.schemas.user import UserRead
from app.services.notifications import Notification

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


@router.post(
    "/verify",
    response_model=UserRead,
    summary="Confirm an email address",
    responses={400: {"description": "The link is invalid or has expired."}},
)
async def verify_email(body: VerificationRequest, session: SessionDep) -> User:
    # read_token, not read_access_token: a link that arrives by email must not
    # double as a credential for calling the API.
    try:
        subject = read_token(body.token, TokenPurpose.verify_email)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is invalid or has expired.",
        ) from None

    user = await session.get(User, int(subject))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is invalid or has expired.",
        )

    # Idempotent: clicking the link twice, which mail clients do on their own
    # when they prefetch links, must not be an error.
    if not user.is_verified:
        user.is_verified = True
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset link",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: SessionDep,
    background: BackgroundTasks,
    notifier: NotifierDep,
) -> dict[str, str]:
    result = await session.exec(select(User).where(User.email == body.email))
    user = result.first()

    # Only send when the account exists, but answer identically either way.
    # "No account with that address" would turn this route into a way to test
    # whether someone banks, shops or ships with FleetLine.
    if user is not None:
        token = create_token(
            str(user.id),
            TokenPurpose.reset_password,
            expires_minutes=settings.reset_token_expire_minutes,
        )
        background.add_task(
            notifier.send,
            Notification(
                channel="email",
                recipient=user.email,
                subject="Reset your FleetLine password",
                body=(
                    f"Hello {user.full_name},\n\n"
                    f"Reset your password by opening:\n"
                    f"{settings.frontend_url}/reset?token={token}\n\n"
                    f"If you did not ask for this, ignore this message; your "
                    f"password has not changed.\n"
                ),
            ),
        )

    return {"detail": "If that address has an account, a reset link is on its way."}


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set a new password using a reset link",
    responses={400: {"description": "The link is invalid or has expired."}},
)
async def reset_password(body: ResetPasswordRequest, session: SessionDep) -> None:
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This reset link is invalid or has expired.",
    )
    try:
        subject = read_token(body.token, TokenPurpose.reset_password)
    except TokenError:
        raise invalid from None

    user = await session.get(User, int(subject))
    if user is None:
        raise invalid

    user.hashed_password = hash_password(body.password)
    # Resetting a password proves control of the mailbox, which is the same
    # thing verification proves, so an unverified account becomes verified here
    # rather than being left in limbo.
    user.is_verified = True
    session.add(user)
    await session.commit()


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
