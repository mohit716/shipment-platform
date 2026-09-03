from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentStaff, CurrentUser
from app.db.session import SessionDep
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseRead

router = APIRouter(prefix="/warehouses", tags=["warehouses"])

# Exported so the shipment router can reuse the same validation for the
# warehouse_id in its /stops routes.
WarehouseId = Annotated[int, Path(ge=1, description="Warehouse reference.")]


async def require_warehouse(session: AsyncSession, warehouse_id: int) -> Warehouse:
    """Return a warehouse row or abort the request with 404."""
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse {warehouse_id} does not exist.",
        )
    return warehouse


@router.post(
    "",
    response_model=WarehouseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a warehouse",
    responses={
        403: {"description": "Only staff may register depots."},
        409: {"description": "That depot code is already registered."},
    },
)
async def create_warehouse(
    body: WarehouseCreate,
    session: SessionDep,
    # Writing the depot network is staff work. Reading it is not: a customer
    # needs to see where their parcel has been.
    current_staff: CurrentStaff,
) -> Warehouse:
    warehouse = Warehouse(**body.model_dump())
    session.add(warehouse)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Depot code {body.code} is already registered.",
        ) from None
    await session.refresh(warehouse)
    return warehouse


@router.get("", response_model=list[WarehouseRead], summary="List warehouses")
async def list_warehouses(
    session: SessionDep,
    current_user: CurrentUser,
    city: Annotated[str | None, Query(description="Filter by city.")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Warehouse]:
    statement = select(Warehouse)
    if city is not None:
        statement = statement.where(Warehouse.city == city)
    statement = statement.order_by(Warehouse.code).offset(offset).limit(limit)
    results = await session.exec(statement)
    return list(results.all())


@router.get(
    "/{warehouse_id}",
    response_model=WarehouseRead,
    summary="Read one warehouse",
    responses={404: {"description": "No warehouse carries that reference."}},
)
async def get_warehouse(
    warehouse_id: WarehouseId,
    session: SessionDep,
    current_user: CurrentUser,
) -> Warehouse:
    return await require_warehouse(session, warehouse_id)
