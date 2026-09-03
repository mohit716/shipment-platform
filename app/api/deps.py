from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.tokens import TokenError, read_access_token
from app.db.session import SessionDep
from app.models.user import User
from app.schemas.user import UserRole
from app.services.notifications import Notifier, get_notifier

# tokenUrl is documentation, not routing: it tells OpenAPI which endpoint hands
# out tokens so Swagger UI's Authorize button knows where to post credentials.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> User:
    """Resolve the bearer token in the Authorization header to a user row.

    Every failure returns the same 401: a missing token, an expired one, a
    forged signature, a subject that is not an integer, and a subject naming an
    account that has since been deleted. The last case is why the database is
    consulted at all rather than trusting the id in the token; a valid signature
    only proves the token was issued, not that the account still exists.
    """
    try:
        subject = read_access_token(token)
    except TokenError:
        raise CREDENTIALS_ERROR from None

    try:
        user_id = int(subject)
    except ValueError:
        raise CREDENTIALS_ERROR from None

    user = await session.get(User, user_id)
    if user is None:
        raise CREDENTIALS_ERROR
    return user


# Writing CurrentUser in a signature both injects the user and documents the
# route as requiring a bearer token in OpenAPI.
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_staff(current_user: CurrentUser) -> User:
    """Require the caller to be staff.

    A dependency that itself depends on get_current_user, so the token is only
    parsed once no matter how deep the chain gets. 403 rather than 404 here: the
    caller is authenticated and the route plainly exists, so hiding it would
    only be confusing. That is the opposite call to shipment ownership, where
    the reference itself is the secret.
    """
    if current_user.role is not UserRole.staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a staff account.",
        )
    return current_user


CurrentStaff = Annotated[User, Depends(get_current_staff)]

# Injected rather than imported, so a test can swap in a notifier that records
# messages instead of sending them, exactly as it swaps the database session.
NotifierDep = Annotated[Notifier, Depends(get_notifier)]
