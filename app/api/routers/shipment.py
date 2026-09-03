import time
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, Query, status
from sqlalchemy.orm import aliased, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentStaff, CurrentUser, NotifierDep
from app.api.routers.tag import TagId, require_tag
from app.api.routers.warehouse import WarehouseId, require_warehouse
from app.db.session import SessionDep
from app.models.package import Package
from app.models.shipment import Shipment
from app.models.tag import ShipmentTagLink, Tag
from app.models.tracking import TrackingEvent
from app.models.user import User
from app.models.warehouse import ShipmentWarehouseLink, Warehouse
from app.schemas.tag import TagRead
from app.schemas.tracking import TrackingEventCreate, TrackingEventRead
from app.schemas.warehouse import WarehouseRead
from app.services.rates import quote_all_carriers
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentRead,
    ShipmentStatus,
    ShipmentUpdate,
    ShipmentWithCustomer,
)
from app.schemas.user import UserRole
from app.services.notifications import Notification

router = APIRouter(prefix="/shipments", tags=["shipments"])

ShipmentId = Annotated[
    int,
    Path(ge=1, description="Shipment reference assigned at booking."),
]


def scope_for(user: User) -> User | None:
    """The ownership restriction to apply for this caller.

    Staff get None, meaning unrestricted. Expressing it as "which owner filter
    applies" rather than sprinkling `if role is staff` through every handler
    keeps the rule in one place, so widening or tightening it is a one-line
    change rather than an audit.
    """
    return None if user.role is UserRole.staff else user


async def require_shipment(
    session: AsyncSession,
    shipment_id: int,
    *,
    owner: User | None = None,
    with_relations: bool = False,
) -> Shipment:
    """Return a shipment row or abort the request with 404.

    with_relations eagerly loads the customer and packages. Any handler that
    touches those collections must ask for them: reading an unloaded
    relationship inside async code raises MissingGreenlet rather than quietly
    emitting an extra query the way sync code would.

    owner enforces that the caller booked the shipment. A shipment belonging to
    somebody else is reported as 404 rather than 403, because 403 confirms the
    reference exists and lets an unauthorised caller map the id space by
    watching which numbers answer differently.
    """
    if with_relations:
        statement = (
            select(Shipment)
            .where(Shipment.id == shipment_id)
            .options(
                selectinload(Shipment.customer),
                selectinload(Shipment.packages),
                selectinload(Shipment.stops),
                selectinload(Shipment.tags),
            )
        )
        shipment = (await session.exec(statement)).first()
    else:
        shipment = await session.get(Shipment, shipment_id)

    if shipment is None or (owner is not None and shipment.customer_id != owner.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} does not exist.",
        )
    return shipment


@router.get("", response_model=list[ShipmentRead], summary="List shipments")
async def list_shipments(
    session: SessionDep,
    current_user: CurrentUser,
    status_filter: Annotated[
        ShipmentStatus | None,
        Query(alias="status", description="Return only shipments in this state."),
    ] = None,
    customer_id: Annotated[
        int | None,
        Query(ge=1, description="Staff only: narrow to one customer."),
    ] = None,
    destination: Annotated[
        int | None,
        Query(ge=10000, le=99999, description="Filter by destination postcode."),
    ] = None,
    tag: Annotated[
        list[str] | None,
        Query(description="Only shipments carrying every one of these labels."),
    ] = None,
    depot: Annotated[
        str | None,
        Query(description="Only shipments routed through this depot code."),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Rows to skip.")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Rows to return.")] = 20,
) -> list[Shipment]:
    # The statement is built up conditionally and only executed at the end, so
    # the unfiltered case never loads the whole table into memory.
    #
    # Scoping in the query rather than filtering the results afterwards means
    # another customer's rows are never loaded at all, and no future filter or
    # pagination bug can widen it.
    statement = select(Shipment)
    scope = scope_for(current_user)
    if scope is not None:
        statement = statement.where(Shipment.customer_id == scope.id)
    elif customer_id is not None:
        # Only staff may ask about somebody else's shipments, which is why the
        # parameter exists again but is read only in this branch.
        statement = statement.where(Shipment.customer_id == customer_id)
    if status_filter is not None:
        statement = statement.where(Shipment.status == status_filter)
    if destination is not None:
        statement = statement.where(Shipment.destination == destination)

    if depot is not None:
        # Two hops to cross a many-to-many: shipments to the link table, then
        # link table to warehouses. Filtering on warehouse.code rather than an
        # id keeps the URL readable: ?depot=LDS1.
        statement = statement.join(ShipmentWarehouseLink).join(Warehouse).where(
            Warehouse.code == depot.strip().upper()
        )

    if tag:
        # AND, not OR. A separate aliased join per label means a row survives
        # only if it matches all of them; a single join with IN would return
        # shipments carrying any one of them, and would also duplicate rows.
        for name in tag:
            link = aliased(ShipmentTagLink)
            labelled = aliased(Tag)
            statement = statement.join(
                link, Shipment.id == link.shipment_id
            ).join(
                labelled, link.tag_id == labelled.id
            ).where(labelled.name == " ".join(name.split()).lower())

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
async def get_shipment(
    shipment_id: ShipmentId,
    session: SessionDep,
    current_user: CurrentUser,
) -> Shipment:
    # Eager loaded, because serialising the nested customer and packages would
    # otherwise touch unloaded relationships and raise MissingGreenlet.
    return await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )


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
async def create_shipment(
    body: ShipmentCreate,
    session: SessionDep,
    current_user: CurrentUser,
    background: BackgroundTasks,
    notifier: NotifierDep,
) -> Shipment:
    # The owner comes from the token, never from the request body. When the
    # client supplied customer_id, anyone could book a shipment in somebody
    # else's name simply by typing their id.
    fields = body.model_dump(exclude={"packages"})
    shipment = Shipment(**fields, customer_id=current_user.id)
    # Appending to the relationship rather than setting shipment_id by hand:
    # SQLAlchemy works out the insert order and fills in the foreign key once
    # the parent has an id, all within one transaction.
    shipment.packages = [Package(**package.model_dump()) for package in body.packages]

    session.add(shipment)
    await session.commit()
    # The id was assigned by the database during commit, so the in-memory
    # object is stale until it is refreshed from the row.
    await session.refresh(shipment)

    # Queued after the commit and run after the response is sent. Sending
    # inline would make the caller wait on a mail server, and sending before
    # the commit would risk confirming a booking that then failed to save.
    background.add_task(
        notifier.send,
        Notification(
            channel="email",
            recipient=current_user.email,
            subject=f"FleetLine booking {shipment.id} confirmed",
            body=(
                f"Hello {current_user.full_name},\n\n"
                f"Your shipment of {shipment.content} to {shipment.destination} "
                f"is booked under reference {shipment.id}.\n"
            ),
        ),
    )
    return shipment


@router.put(
    "/{shipment_id}",
    response_model=ShipmentWithCustomer,
    summary="Replace a shipment",
)
async def replace_shipment(
    shipment_id: ShipmentId,
    body: ShipmentCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Shipment:
    # with_relations is required here: replacing the packages list compares it
    # against the current one, and comparing against an unloaded collection
    # would trigger a lazy load.
    shipment = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )

    for field, value in body.model_dump(exclude={"packages"}).items():
        setattr(shipment, field, value)

    # PUT replaces, so the old boxes go. delete-orphan on the relationship is
    # what turns "removed from this list" into "deleted from the table".
    shipment.packages = [Package(**package.model_dump()) for package in body.packages]

    session.add(shipment)
    await session.commit()
    return await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )


@router.patch(
    "/{shipment_id}",
    response_model=ShipmentRead,
    summary="Update part of a shipment",
)
async def update_shipment(
    shipment_id: ShipmentId,
    body: ShipmentUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Shipment:
    shipment = await require_shipment(session, shipment_id, owner=scope_for(current_user))
    # exclude_unset keeps fields the client never mentioned out of the update,
    # which is the difference between "leave it alone" and "set it to null".
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(shipment, field, value)
    session.add(shipment)
    await session.commit()
    await session.refresh(shipment)
    return shipment


@router.get(
    "/{shipment_id}/tracking",
    response_model=list[TrackingEventRead],
    summary="Read a shipment's tracking timeline",
    responses={404: {"description": "No shipment carries that reference."}},
)
async def list_tracking_events(
    shipment_id: ShipmentId,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[TrackingEvent]:
    await require_shipment(session, shipment_id, owner=scope_for(current_user))
    statement = (
        select(TrackingEvent)
        .where(TrackingEvent.shipment_id == shipment_id)
        # id breaks ties: two scans recorded in the same microsecond would
        # otherwise come back in arbitrary order.
        .order_by(TrackingEvent.recorded_at, TrackingEvent.id)
    )
    results = await session.exec(statement)
    return list(results.all())


@router.post(
    "/{shipment_id}/tracking",
    response_model=TrackingEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a tracking scan",
    responses={
        403: {"description": "Only staff may record scans."},
        404: {"description": "No shipment carries that reference."},
    },
)
async def add_tracking_event(
    shipment_id: ShipmentId,
    body: TrackingEventCreate,
    session: SessionDep,
    # Scans are staff-only even though reading the timeline is not. A customer
    # who can write their own scans can declare a parcel delivered, and the
    # timeline is meant to be evidence rather than a claim.
    current_staff: CurrentStaff,
    background: BackgroundTasks,
    notifier: NotifierDep,
) -> TrackingEvent:
    shipment = await require_shipment(session, shipment_id, with_relations=True)

    event = TrackingEvent(shipment_id=shipment_id, **body.model_dump())
    session.add(event)
    # The scan is the source of truth, so the shipment's current status follows
    # from it. Both writes share one transaction: the timeline and the summary
    # cannot disagree.
    previous_status = shipment.status
    shipment.status = body.status
    session.add(shipment)

    await session.commit()
    await session.refresh(event)

    # Only on an actual change. Depots rescan parcels routinely, and a customer
    # who gets a text every time a barcode is read will stop reading them.
    if body.status is not previous_status:
        background.add_task(
            notifier.send,
            Notification(
                channel="email",
                recipient=shipment.customer.email,
                subject=f"Shipment {shipment.id} is now {body.status.value}",
                body=(
                    f"Hello {shipment.customer.full_name},\n\n"
                    f"Your shipment {shipment.id} was scanned at "
                    f"{body.location} and is now {body.status.value}.\n"
                ),
            ),
        )
    return event


@router.get(
    "/{shipment_id}/stops",
    response_model=list[WarehouseRead],
    summary="List a shipment's routing stops",
    responses={404: {"description": "No shipment carries that reference."}},
)
async def list_stops(
    shipment_id: ShipmentId,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[Warehouse]:
    shipment = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    return shipment.stops


@router.put(
    "/{shipment_id}/stops/{warehouse_id}",
    response_model=list[WarehouseRead],
    summary="Add a routing stop",
    responses={404: {"description": "No such shipment or warehouse."}},
)
async def attach_stop(
    shipment_id: ShipmentId,
    warehouse_id: WarehouseId,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[Warehouse]:
    shipment = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    warehouse = await require_warehouse(session, warehouse_id)

    # PUT, so attaching twice is idempotent. Appending unconditionally would
    # violate the link table's composite primary key on the second call.
    if warehouse not in shipment.stops:
        shipment.stops.append(warehouse)
        session.add(shipment)
        await session.commit()

    refreshed = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    return refreshed.stops


@router.delete(
    "/{shipment_id}/stops/{warehouse_id}",
    response_model=list[WarehouseRead],
    summary="Remove a routing stop",
    responses={404: {"description": "No such shipment or warehouse."}},
)
async def detach_stop(
    shipment_id: ShipmentId,
    warehouse_id: WarehouseId,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[Warehouse]:
    shipment = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    warehouse = await require_warehouse(session, warehouse_id)

    # Removing from the list deletes the link row only. The warehouse itself is
    # a shared entity and must survive being dropped from one shipment's route.
    if warehouse in shipment.stops:
        shipment.stops.remove(warehouse)
        session.add(shipment)
        await session.commit()

    refreshed = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    return refreshed.stops


@router.get(
    "/{shipment_id}/tags",
    response_model=list[TagRead],
    summary="List a shipment's handling labels",
    responses={404: {"description": "No shipment carries that reference."}},
)
async def list_shipment_tags(
    shipment_id: ShipmentId,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[Tag]:
    shipment = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    return shipment.tags


@router.put(
    "/{shipment_id}/tags/{tag_id}",
    response_model=list[TagRead],
    summary="Apply a handling label",
    responses={404: {"description": "No such shipment or tag."}},
)
async def attach_tag(
    shipment_id: ShipmentId,
    tag_id: TagId,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[Tag]:
    shipment = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    tag = await require_tag(session, tag_id)

    if tag not in shipment.tags:
        shipment.tags.append(tag)
        session.add(shipment)
        await session.commit()

    refreshed = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    return refreshed.tags


@router.delete(
    "/{shipment_id}/tags/{tag_id}",
    response_model=list[TagRead],
    summary="Remove a handling label",
    responses={404: {"description": "No such shipment or tag."}},
)
async def detach_tag(
    shipment_id: ShipmentId,
    tag_id: TagId,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[Tag]:
    shipment = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    tag = await require_tag(session, tag_id)

    if tag in shipment.tags:
        shipment.tags.remove(tag)
        session.add(shipment)
        await session.commit()

    refreshed = await require_shipment(
        session, shipment_id, owner=scope_for(current_user), with_relations=True
    )
    return refreshed.tags


@router.delete(
    "/{shipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a shipment",
)
async def delete_shipment(
    shipment_id: ShipmentId,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    shipment = await require_shipment(session, shipment_id, owner=scope_for(current_user))
    await session.delete(shipment)
    await session.commit()
