from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, status

from app.schemas.shipment import ShipmentCreate, ShipmentRead, ShipmentUpdate

router = APIRouter(prefix="/shipments", tags=["shipments"])

# Stand-in for a database while the HTTP layer is being built. Everything here is
# lost when the process restarts; PostgreSQL replaces it in a later phase.
shipments: dict[int, dict[str, Any]] = {
    12701: {
        "id": 12701,
        "content": "ceramic dinnerware",
        "weight_kg": 2.4,
        "destination": 11001,
        "status": "in_transit",
    },
    12702: {
        "id": 12702,
        "content": "laptop parts",
        "weight_kg": 0.9,
        "destination": 40015,
        "status": "placed",
    },
}

ShipmentId = Annotated[
    int,
    Path(ge=10000, le=99999, description="Five digit shipment reference."),
]


def require_shipment(shipment_id: int) -> dict[str, Any]:
    """Return a shipment or abort the request with 404."""
    shipment = shipments.get(shipment_id)
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} does not exist.",
        )
    return shipment


@router.get("", response_model=list[ShipmentRead], summary="List every shipment")
def list_shipments() -> list[dict[str, Any]]:
    return list(shipments.values())


@router.get(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Read one shipment",
    responses={404: {"description": "No shipment carries that reference."}},
)
def get_shipment(shipment_id: ShipmentId) -> dict[str, Any]:
    return require_shipment(shipment_id)


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
def create_shipment(body: ShipmentCreate) -> dict[str, Any]:
    new_id = max(shipments) + 1
    shipments[new_id] = {"id": new_id, **body.model_dump()}
    return shipments[new_id]


@router.put(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Replace a shipment",
)
def replace_shipment(shipment_id: ShipmentId, body: ShipmentCreate) -> dict[str, Any]:
    # PUT is a full replacement: the stored record becomes exactly what was sent,
    # so any field the client omits falls back to the schema default.
    require_shipment(shipment_id)
    shipments[shipment_id] = {"id": shipment_id, **body.model_dump()}
    return shipments[shipment_id]


@router.patch(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Update part of a shipment",
)
def update_shipment(shipment_id: ShipmentId, body: ShipmentUpdate) -> dict[str, Any]:
    shipment = require_shipment(shipment_id)
    # exclude_unset keeps fields the client never mentioned out of the update,
    # which is the difference between "leave it alone" and "set it to null".
    shipment.update(body.model_dump(exclude_unset=True))
    return shipment


@router.delete(
    "/{shipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a shipment",
)
def delete_shipment(shipment_id: ShipmentId) -> None:
    shipments.pop(shipment_id, None)
