from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status

from app.api.routers import shipment
from app.db.session import create_db_and_tables

DESCRIPTION = """
FleetLine moves parcels from a customer's door to a delivery address, through
carriers and warehouse stops, and reports where each one is.

Every shipment carries a lifecycle status, and each change to it is recorded so
the customer can see the full journey rather than only the latest position.
"""

TAGS_METADATA = [
    {
        "name": "shipments",
        "description": "Book, amend, track and cancel shipments.",
    },
    {
        "name": "system",
        "description": "Operational endpoints used by load balancers and monitors.",
    },
]

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run once on startup, and again after yield on shutdown.

    This replaced the older @app.on_event("startup") decorators, which are
    deprecated. Everything before yield happens before the first request is
    served; everything after runs during a clean shutdown.
    """
    await create_db_and_tables()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="FleetLine",
    description=DESCRIPTION,
    version="0.1.0",
    summary="Shipment management platform.",
    openapi_tags=TAGS_METADATA,
    contact={"name": "Mohit Sharma", "url": "https://github.com/mohit716"},
    license_info={"name": "MIT"},
)

app.include_router(shipment.router)


@app.get("/", tags=["system"], summary="Service banner")
def read_root() -> dict[str, str]:
    return {"service": "FleetLine", "docs": "/docs"}


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    tags=["system"],
    summary="Liveness probe",
    response_description="The service is accepting traffic.",
)
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
