from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlmodel import Session, select

from app.db.session import SessionDep
from app.models.shipment import Shipment
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentRead,
    ShipmentStatus,
    ShipmentUpdate,
)

router = APIRouter(prefix="/shipments", tags=["shipments"])

ShipmentId = Annotated[
    int,
    Path(ge=1, description="Shipment reference assigned at booking."),
]


def require_shipment(session: Session, shipment_id: int) -> Shipment:
    """Return a shipment row or abort the request with 404."""
    shipment = session.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} does not exist.",
        )
    return shipment


@router.get("", response_model=list[ShipmentRead], summary="List shipments")
def list_shipments(
    session: SessionDep,
    status_filter: Annotated[
        ShipmentStatus | None,
        Query(alias="status", description="Return only shipments in this state."),
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
    if destination is not None:
        statement = statement.where(Shipment.destination == destination)
    statement = statement.order_by(Shipment.id).offset(offset).limit(limit)
    return list(session.exec(statement).all())


@router.get(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Read one shipment",
    responses={404: {"description": "No shipment carries that reference."}},
)
def get_shipment(shipment_id: ShipmentId, session: SessionDep) -> Shipment:
    return require_shipment(session, shipment_id)


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
def create_shipment(body: ShipmentCreate, session: SessionDep) -> Shipment:
    shipment = Shipment(**body.model_dump())
    session.add(shipment)
    session.commit()
    # The id was assigned by the database during commit, so the in-memory
    # object is stale until it is refreshed from the row.
    session.refresh(shipment)
    return shipment


@router.put(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Replace a shipment",
)
def replace_shipment(
    shipment_id: ShipmentId,
    body: ShipmentCreate,
    session: SessionDep,
) -> Shipment:
    shipment = require_shipment(session, shipment_id)
    for field, value in body.model_dump().items():
        setattr(shipment, field, value)
    session.add(shipment)
    session.commit()
    session.refresh(shipment)
    return shipment


@router.patch(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Update part of a shipment",
)
def update_shipment(
    shipment_id: ShipmentId,
    body: ShipmentUpdate,
    session: SessionDep,
) -> Shipment:
    shipment = require_shipment(session, shipment_id)
    # exclude_unset keeps fields the client never mentioned out of the update,
    # which is the difference between "leave it alone" and "set it to null".
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(shipment, field, value)
    session.add(shipment)
    session.commit()
    session.refresh(shipment)
    return shipment


@router.delete(
    "/{shipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a shipment",
)
def delete_shipment(shipment_id: ShipmentId, session: SessionDep) -> None:
    shipment = require_shipment(session, shipment_id)
    session.delete(shipment)
    session.commit()
