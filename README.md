# FleetLine

A shipment management platform. Customers book shipments, warehouses and carriers
move them through a delivery lifecycle, and every status change is recorded as a
tracking event and pushed to the customer by email and SMS.

Built with FastAPI, PostgreSQL, Redis, Celery and React.

> Status: in active development. The commit history is intentionally fine grained,
> with each commit introducing a single concept.

## Planned capabilities

- Shipment booking with packages, routing stops and labels such as Fragile or Perishable.
- A delivery lifecycle: placed, picked up, in transit, at warehouse, out for delivery, delivered.
- A tracking timeline recording who changed what and when.
- Role based access for customers, warehouse staff, carriers and administrators.
- Email and SMS notifications delivered asynchronously by background workers.
- A React dashboard for booking, searching and tracking shipments.

## Tech stack

| Layer | Technology |
| --- | --- |
| API | FastAPI, Pydantic v2 |
| Database | PostgreSQL, SQLModel, Alembic |
| Background work | Celery, Redis |
| Frontend | React, TypeScript, Vite |
| Testing | pytest, httpx |
| Delivery | Docker Compose, GitHub Actions |

## Running locally

Requires Python 3.10 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is then available at http://127.0.0.1:8000.

| Route | Purpose |
| --- | --- |
| `/` | Service banner |
| `/health` | Liveness probe |
| `/docs` | Interactive Swagger UI |
| `/redoc` | Reference documentation |

## Project layout

```
app/
  main.py        # application instance and system routes
requirements.txt # pinned direct dependencies
```

This tree grows as the project develops; see the commit history for how and why.
