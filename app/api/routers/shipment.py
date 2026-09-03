from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, status

from app.schemas.shipment import Shipment

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


@router.get("", summary="List every shipment")
def list_shipments() -> list[dict[str, Any]]:
    return list(shipments.values())


@router.get("/{shipment_id}", summary="Read one shipment")
def get_shipment(shipment_id: ShipmentId) -> dict[str, Any]:
    return require_shipment(shipment_id)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Book a shipment")
def create_shipment(body: Shipment) -> dict[str, Any]:
    new_id = max(shipments) + 1
    shipments[new_id] = {"id": new_id, **body.model_dump()}
    return shipments[new_id]


@router.put("/{shipment_id}", summary="Replace a shipment")
def replace_shipment(shipment_id: ShipmentId, body: Shipment) -> dict[str, Any]:
    # PUT is a full replacement: the stored record becomes exactly what was sent,
    # so any field the client omits is dropped.
    require_shipment(shipment_id)
    shipments[shipment_id] = {"id": shipment_id, **body.model_dump()}
    return shipments[shipment_id]


@router.patch("/{shipment_id}", summary="Update part of a shipment")
def update_shipment(shipment_id: ShipmentId, body: dict[str, Any]) -> dict[str, Any]:
    # PATCH still takes a raw dict: a partial update needs every field optional,
    # which is a separate schema. Commit 18 introduces it.
    shipment = require_shipment(shipment_id)
    shipment.update(body)
    return shipment


@router.delete(
    "/{shipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a shipment",
)
def delete_shipment(shipment_id: ShipmentId) -> None:
    shipments.pop(shipment_id, None)
