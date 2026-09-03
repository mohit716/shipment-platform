from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.db.session import SessionDep
from app.models.shipment import Shipment
from app.models.user import User
from app.schemas.shipment import ShipmentRead
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])

UserId = Annotated[int, Path(ge=1, description="Customer reference.")]


async def require_user(session: AsyncSession, user_id: int) -> User:
    """Return a user row or abort the request with 404."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {user_id} does not exist.",
        )
    return user


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a customer",
    responses={409: {"description": "That email address is already registered."}},
)
async def create_user(body: UserCreate, session: SessionDep) -> User:
    # The plaintext password exists only inside this function. It is hashed
    # before the row is built, so it never reaches the model, the session, the
    # database, or a log line that dumps the object.
    payload = body.model_dump(exclude={"password"})
    user = User(**payload, hashed_password=hash_password(body.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # The unique constraint is enforced by the database, so a duplicate is
        # caught here rather than by a check-then-insert, which two concurrent
        # requests could both pass before either wrote.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{body.email} is already registered.",
        ) from None
    await session.refresh(user)
    return user


@router.get("", response_model=list[UserRead], summary="List customers")
async def list_users(
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[User]:
    statement = select(User).order_by(User.id).offset(offset).limit(limit)
    results = await session.exec(statement)
    return list(results.all())


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Read one customer",
    responses={404: {"description": "No customer carries that reference."}},
)
async def get_user(user_id: UserId, session: SessionDep) -> User:
    return await require_user(session, user_id)


@router.get(
    "/{user_id}/shipments",
    response_model=list[ShipmentRead],
    summary="List a customer's shipments",
    responses={404: {"description": "No customer carries that reference."}},
)
async def list_user_shipments(user_id: UserId, session: SessionDep) -> list[Shipment]:
    # Reading user.shipments would lazily emit a query on attribute access, and
    # a lazy load in async code raises MissingGreenlet. selectinload fetches the
    # children up front as part of this statement instead.
    statement = (
        select(User).where(User.id == user_id).options(selectinload(User.shipments))
    )
    user = (await session.exec(statement)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {user_id} does not exist.",
        )
    return user.shipments
