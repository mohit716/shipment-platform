from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlmodel import Session, select

from app.db.session import engine
from app.models.shipment import Shipment
from app.schemas.shipment import ShipmentCreate, ShipmentRead, ShipmentUpdate

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


@router.get("", response_model=list[ShipmentRead], summary="List every shipment")
def list_shipments() -> list[Shipment]:
    with Session(engine) as session:
        return list(session.exec(select(Shipment)).all())


@router.get(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Read one shipment",
    responses={404: {"description": "No shipment carries that reference."}},
)
def get_shipment(shipment_id: ShipmentId) -> Shipment:
    with Session(engine) as session:
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
def create_shipment(body: ShipmentCreate) -> Shipment:
    with Session(engine) as session:
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
def replace_shipment(shipment_id: ShipmentId, body: ShipmentCreate) -> Shipment:
    with Session(engine) as session:
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
def update_shipment(shipment_id: ShipmentId, body: ShipmentUpdate) -> Shipment:
    with Session(engine) as session:
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
def delete_shipment(shipment_id: ShipmentId) -> None:
    with Session(engine) as session:
        shipment = require_shipment(session, shipment_id)
        session.delete(shipment)
        session.commit()
