"""Load a demo dataset so the dashboard has something to show.

Idempotent: running it twice does not duplicate rows. It looks up the demo
accounts by email and skips the rest if they already exist, which is what you
want after a crash halfway through and also what you want on every deploy that
should not wipe production data.

    python -m app.seed
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.package import Package
from app.models.shipment import Shipment
from app.models.tag import Tag
from app.models.tracking import TrackingEvent
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.shipment import ShipmentStatus
from app.schemas.user import UserRole

DEMO_PASSWORD = "correct-horse"

CUSTOMER_EMAIL = "ada@example.com"
STAFF_EMAIL = "depot@fleetline.example"


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        existing = (
            await session.exec(select(User).where(User.email == CUSTOMER_EMAIL))
        ).first()
        if existing is not None:
            print("Demo data already present; nothing to do.")
            return

        password = hash_password(DEMO_PASSWORD)

        ada = User(
            email=CUSTOMER_EMAIL,
            full_name="Ada Lovelace",
            hashed_password=password,
            role=UserRole.customer,
            is_verified=True,
        )
        depot_op = User(
            email=STAFF_EMAIL,
            full_name="Depot Operator",
            hashed_password=password,
            role=UserRole.staff,
            is_verified=True,
        )
        session.add(ada)
        session.add(depot_op)
        await session.flush()

        leeds = Warehouse(code="LDS1", name="Leeds Central Depot", city="Leeds")
        newcastle = Warehouse(code="NCL1", name="Newcastle Hub", city="Newcastle")
        manchester = Warehouse(code="MAN1", name="Manchester Sort", city="Manchester")
        session.add(leeds)
        session.add(newcastle)
        session.add(manchester)

        fragile = Tag(name="fragile", requires_signature=True)
        perishable = Tag(name="perishable", requires_signature=False)
        session.add(fragile)
        session.add(perishable)
        await session.flush()

        now = datetime.now(timezone.utc)

        dinnerware = Shipment(
            content="ceramic dinnerware, double boxed",
            weight_kg=2.4,
            destination=11001,
            customer_id=ada.id,
            status=ShipmentStatus.in_transit,
            created_at=now - timedelta(days=2),
        )
        dinnerware.packages = [
            Package(
                description="outer carton",
                weight_kg=2.4,
                length_cm=40,
                width_cm=30,
                height_cm=20,
            )
        ]
        dinnerware.stops = [leeds, newcastle]
        dinnerware.tags = [fragile]
        dinnerware.tracking_events = [
            TrackingEvent(
                status=ShipmentStatus.placed,
                location="Online booking",
                note="Booked by Ada Lovelace",
                recorded_at=now - timedelta(days=2),
            ),
            TrackingEvent(
                status=ShipmentStatus.picked_up,
                location="Leeds Central Depot",
                recorded_at=now - timedelta(days=1, hours=20),
            ),
            TrackingEvent(
                status=ShipmentStatus.in_transit,
                location="M1 northbound",
                recorded_at=now - timedelta(hours=6),
            ),
        ]
        session.add(dinnerware)

        laptop = Shipment(
            content="laptop parts",
            weight_kg=4.1,
            destination=11002,
            customer_id=ada.id,
            status=ShipmentStatus.placed,
            created_at=now - timedelta(hours=3),
        )
        laptop.packages = [
            Package(
                description="main chassis",
                weight_kg=3.0,
                length_cm=50,
                width_cm=35,
                height_cm=10,
            ),
            Package(
                description="spares box",
                weight_kg=1.1,
                length_cm=20,
                width_cm=15,
                height_cm=10,
            ),
        ]
        laptop.tags = [fragile]
        session.add(laptop)

        flowers = Shipment(
            content="cut flowers, chilled",
            weight_kg=1.2,
            destination=11003,
            customer_id=ada.id,
            status=ShipmentStatus.delivered,
            created_at=now - timedelta(days=5),
        )
        flowers.packages = [
            Package(
                description="chilled sleeve",
                weight_kg=1.2,
                length_cm=60,
                width_cm=15,
                height_cm=15,
            )
        ]
        flowers.stops = [manchester]
        flowers.tags = [perishable]
        flowers.tracking_events = [
            TrackingEvent(
                status=ShipmentStatus.placed,
                location="Online booking",
                recorded_at=now - timedelta(days=5),
            ),
            TrackingEvent(
                status=ShipmentStatus.delivered,
                location="Customer address",
                recorded_at=now - timedelta(days=4),
            ),
        ]
        session.add(flowers)

        await session.commit()
        print(
            "Seeded demo data.\n"
            f"  customer  {CUSTOMER_EMAIL} / {DEMO_PASSWORD}\n"
            f"  staff     {STAFF_EMAIL} / {DEMO_PASSWORD}"
        )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
