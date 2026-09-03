from fastapi import FastAPI, status

from app.api.routers import shipment

app = FastAPI(
    title="FleetLine",
    description="Shipment management platform.",
    version="0.1.0",
)

app.include_router(shipment.router)


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
