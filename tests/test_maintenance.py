from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from app.models.shipment import Shipment
from app.models.user import User
from app.schemas.shipment import ShipmentStatus
from app.services.notifications import MemoryNotifier
from app.tasks import maintenance


def build_database(tmp_path, rows) -> None:
    """A synchronous throwaway database matching the worker's own engine.

    The worker uses a plain Session rather than an AsyncSession, so this test
    does too. Reaching for the async client fixture here would test something
    the task never does.
    """
    engine = create_engine(f"sqlite:///{(tmp_path / 'worker.db').as_posix()}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for row in rows:
            session.add(row)
        session.commit()
    return engine


def customer() -> User:
    return User(
        email="ada@example.com",
        full_name="Ada Lovelace",
        hashed_password="!",
    )


def shipment(days_old: int, status: ShipmentStatus) -> Shipment:
    return Shipment(
        content="ceramic dinnerware",
        weight_kg=2.4,
        destination=11001,
        status=status,
        customer_id=1,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_old),
    )


def run_task(monkeypatch, tmp_path, rows) -> tuple[int, MemoryNotifier]:
    engine = build_database(tmp_path, rows)
    outbox = MemoryNotifier()
    monkeypatch.setattr(maintenance, "_sync_engine", lambda: engine)
    monkeypatch.setattr(maintenance, "build_notifier", lambda: outbox)
    return maintenance.flag_stalled_shipments(), outbox


def test_an_old_uncollected_shipment_is_flagged(monkeypatch, tmp_path) -> None:
    rows = [customer(), shipment(5, ShipmentStatus.placed)]
    flagged, outbox = run_task(monkeypatch, tmp_path, rows)

    assert flagged == 1
    assert "has not been collected" in outbox.sent[0].subject


def test_a_recent_shipment_is_left_alone(monkeypatch, tmp_path) -> None:
    rows = [customer(), shipment(1, ShipmentStatus.placed)]
    flagged, outbox = run_task(monkeypatch, tmp_path, rows)

    # One day old is inside the two day window; warning here would train
    # customers to ignore the warning.
    assert flagged == 0
    assert outbox.sent == []


def test_an_old_shipment_that_moved_is_left_alone(monkeypatch, tmp_path) -> None:
    rows = [customer(), shipment(5, ShipmentStatus.in_transit)]
    flagged, _ = run_task(monkeypatch, tmp_path, rows)

    # Age alone is not the problem. A five day old parcel already in transit is
    # simply travelling.
    assert flagged == 0


def test_the_task_reports_how_many_it_flagged(monkeypatch, tmp_path) -> None:
    rows = [
        customer(),
        shipment(5, ShipmentStatus.placed),
        shipment(9, ShipmentStatus.placed),
        shipment(1, ShipmentStatus.placed),
    ]
    flagged, _ = run_task(monkeypatch, tmp_path, rows)

    # The return value lands in the result backend, so a scheduled run leaves a
    # number behind rather than only a log line.
    assert flagged == 2


def test_the_schedule_is_registered() -> None:
    from app.worker import celery_app

    entry = celery_app.conf.beat_schedule["flag-stalled-shipments-hourly"]
    assert entry["task"] == "maintenance.flag_stalled_shipments"
    assert entry["schedule"] == 3600.0
