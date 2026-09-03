from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, shipment, tag, user, warehouse
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

DESCRIPTION = """
FleetLine moves parcels from a customer's door to a delivery address, through
carriers and warehouse stops, and reports where each one is.

Every shipment carries a lifecycle status, and each change to it is recorded so
the customer can see the full journey rather than only the latest position.
"""

TAGS_METADATA = [
    {
        "name": "auth",
        "description": "Exchange credentials for an access token.",
    },
    {
        "name": "users",
        "description": "Customers who book shipments.",
    },
    {
        "name": "warehouses",
        "description": "Depots and sorting hubs shipments are routed through.",
    },
    {
        "name": "tags",
        "description": "Handling labels applied to shipments.",
    },
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

    Creating tables no longer happens here. The schema is owned by Alembic, so
    starting the app can never silently change the database: run
    `alembic upgrade head` instead.
    """
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    description=DESCRIPTION,
    version="0.1.0",
    summary="Shipment management platform.",
    openapi_tags=TAGS_METADATA,
    contact={"name": "Mohit Sharma", "url": "https://github.com/mohit716"},
    license_info={"name": "MIT"},
)

# A browser refuses to let JavaScript on one origin read a response from
# another unless the server says so. The dashboard runs on a different port
# during development, which is a different origin, so without this every fetch
# from it fails in the browser while the same request from curl succeeds.
app.add_middleware(
    CORSMiddleware,
    # An explicit list, not "*". A wildcard cannot be combined with credentials,
    # and allowing any site to call the API with a user's token is exactly what
    # the rule exists to prevent.
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    # Authorization is not in the browser's default safelist, so a preflight
    # that does not mention it rejects every authenticated request.
    allow_headers=["Authorization", "Content-Type"],
)

# Registered after CORS and therefore the outermost layer, because middleware
# wraps in reverse order of registration. That is what makes the timing cover
# the entire response, preflights included, and sets the request id before any
# other code can log.
app.add_middleware(RequestContextMiddleware)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(warehouse.router)
app.include_router(tag.router)
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
    return {
        "status": "ok",
        "version": app.version,
        "environment": settings.environment,
    }
