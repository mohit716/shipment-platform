from typing import Annotated, Any

from fastapi import FastAPI, Path, status

app = FastAPI(
    title="FleetLine",
    description="Shipment management platform.",
    version="0.1.0",
)

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


@app.get("/")
def read_root() -> dict[str, str]:
    return {"service": "FleetLine", "docs": "/docs"}


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    tags=["system"],
    summary="Liveness probe",
)
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/shipments", tags=["shipments"], summary="List every shipment")
def list_shipments() -> list[dict[str, Any]]:
    return list(shipments.values())


@app.get("/shipments/{shipment_id}", tags=["shipments"], summary="Read one shipment")
def get_shipment(
    shipment_id: Annotated[
        int,
        Path(
            ge=10000,
            le=99999,
            description="Five digit shipment reference.",
        ),
    ],
) -> dict[str, Any] | None:
    return shipments.get(shipment_id)


@app.post(
    "/shipments",
    status_code=status.HTTP_201_CREATED,
    tags=["shipments"],
    summary="Book a shipment",
)
def create_shipment(body: dict[str, Any]) -> dict[str, Any]:
    # Accepting a bare dict means anything at all is accepted: missing fields,
    # a weight of "heavy", unknown keys. Pydantic models fix this in phase 2.
    new_id = max(shipments) + 1
    shipments[new_id] = {"id": new_id, **body}
    return shipments[new_id]
