import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.routers.user import require_user
from app.db.session import SessionDep
from app.models.shipment import Shipment
from app.services.rates import quote_all_carriers
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentRead,
    ShipmentStatus,
    ShipmentUpdate,
    ShipmentWithCustomer,
)

router = APIRouter(prefix="/shipments", tags=["shipments"])

ShipmentId = Annotated[
    int,
    Path(ge=1, description="Shipment reference assigned at booking."),
]


async def require_shipment(session: AsyncSession, shipment_id: int) -> Shipment:
    """Return a shipment row or abort the request with 404."""
    shipment = await session.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} does not exist.",
        )
    return shipment


@router.get("", response_model=list[ShipmentRead], summary="List shipments")
async def list_shipments(
    session: SessionDep,
    status_filter: Annotated[
        ShipmentStatus | None,
        Query(alias="status", description="Return only shipments in this state."),
    ] = None,
    customer_id: Annotated[
        int | None,
        Query(ge=1, description="Filter to one customer's shipments."),
    ] = None,
    destination: Annotated[
        int | None,
        Query(ge=10000, le=99999, description="Filter by destination postcode."),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Rows to skip.")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Rows to return.")] = 20,
) -> list[Shipment]:
    # The statement is built up conditionally and only executed at the end, so
    # the unfiltered case never loads the whole table into memory.
    statement = select(Shipment)
    if status_filter is not None:
        statement = statement.where(Shipment.status == status_filter)
    if customer_id is not None:
        statement = statement.where(Shipment.customer_id == customer_id)
    if destination is not None:
        statement = statement.where(Shipment.destination == destination)
    statement = statement.order_by(Shipment.id).offset(offset).limit(limit)
    results = await session.exec(statement)
    return list(results.all())


@router.get(
    "/quotes",
    summary="Compare carrier rates",
    response_description="Every carrier's price, cheapest first.",
)
async def compare_carrier_rates(
    weight_kg: Annotated[float, Query(gt=0, le=25)],
) -> dict[str, object]:
    # Declared before /{shipment_id} on purpose: the parameterised route would
    # otherwise match "quotes" first and fail validation with a 422.
    started = time.perf_counter()
    quotes = await quote_all_carriers(weight_kg)
    return {
        "weight_kg": weight_kg,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "sequential_would_take": round(sum(q.latency_seconds for q in quotes), 3),
        "quotes": [
            {"carrier": q.carrier, "price": q.price, "latency": q.latency_seconds}
            for q in quotes
        ],
    }


@router.get(
    "/{shipment_id}",
    response_model=ShipmentWithCustomer,
    summary="Read one shipment",
    responses={404: {"description": "No shipment carries that reference."}},
)
async def get_shipment(shipment_id: ShipmentId, session: SessionDep) -> Shipment:
    # One statement, one round trip. Without the eager load, serialising the
    # nested customer would touch shipment.customer and trigger a lazy query,
    # which raises MissingGreenlet under async.
    statement = (
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.customer))
    )
    shipment = (await session.exec(statement)).first()
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} does not exist.",
        )
    return shipment


@router.post(
    "",
    response_model=ShipmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Book a shipment",
    response_description="The booked shipment, including its assigned reference.",
    responses={
        422: {"description": "The parcel breaches a weight, size or content rule."}
    },
)
async def create_shipment(body: ShipmentCreate, session: SessionDep) -> Shipment:
    # Checked explicitly so an unknown customer produces a clear 404 rather than
    # a foreign key violation surfacing as a 500.
    await require_user(session, body.customer_id)
    shipment = Shipment(**body.model_dump())
    session.add(shipment)
    await session.commit()
    # The id was assigned by the database during commit, so the in-memory
    # object is stale until it is refreshed from the row.
    await session.refresh(shipment)
    return shipment


@router.put(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Replace a shipment",
)
async def replace_shipment(
    shipment_id: ShipmentId,
    body: ShipmentCreate,
    session: SessionDep,
) -> Shipment:
    shipment = await require_shipment(session, shipment_id)
    for field, value in body.model_dump().items():
        setattr(shipment, field, value)
    session.add(shipment)
    await session.commit()
    await session.refresh(shipment)
    return shipment


@router.patch(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Update part of a shipment",
)
async def update_shipment(
    shipment_id: ShipmentId,
    body: ShipmentUpdate,
    session: SessionDep,
) -> Shipment:
    shipment = await require_shipment(session, shipment_id)
    # exclude_unset keeps fields the client never mentioned out of the update,
    # which is the difference between "leave it alone" and "set it to null".
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(shipment, field, value)
    session.add(shipment)
    await session.commit()
    await session.refresh(shipment)
    return shipment


@router.delete(
    "/{shipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a shipment",
)
async def delete_shipment(shipment_id: ShipmentId, session: SessionDep) -> None:
    shipment = await require_shipment(session, shipment_id)
    await session.delete(shipment)
    await session.commit()
