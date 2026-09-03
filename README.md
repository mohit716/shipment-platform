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
cp .env.example .env            # then set SECRET_KEY

docker compose up -d db         # PostgreSQL on port 5433
alembic upgrade head            # build the schema

uvicorn app.main:app --reload
```

Background work is optional. To run it, start Redis and set
`CELERY_ENABLED=true`, then in two more terminals:

```bash
docker compose up -d redis
celery -A app.worker.celery_app worker --loglevel=info   # does the work
celery -A app.worker.celery_app beat   --loglevel=info   # publishes on a timer
```

With `CELERY_ENABLED=false` the same notifications are delivered inline, so the
API runs with nothing but Python and a database.

Load a dataset the dashboard can show:

```bash
python -m app.seed
```

Safe to run twice: the second time it sees the demo accounts and stops. The
accounts it creates:

| Role | Email | Password |
| --- | --- | --- |
| Customer | ada@example.com | correct-horse |
| Staff | depot@fleetline.example | correct-horse |

Ada has three shipments: one in transit through Leeds and Newcastle, one just
booked, and one already delivered. Log in at `/docs` with the OAuth2 password
flow (`username` is the email) and `GET /shipments` to walk the same data the
dashboard uses.

The API is then available at http://127.0.0.1:8000.

| Route | Purpose |
| --- | --- |
| `/` | Service banner |
| `/health` | Liveness probe |
| `/docs` | Interactive Swagger UI |
| `/redoc` | Reference documentation |

## Authentication

Every route except registration, login and the system probes needs a bearer
token.

```bash
# 1. Register. New accounts are always customers.
curl -X POST http://127.0.0.1:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com","full_name":"Ada Lovelace","password":"correct-horse"}'

# 2. Exchange credentials for a token. Form encoded, as OAuth2 specifies.
curl -X POST http://127.0.0.1:8000/auth/token \
  -d 'username=ada@example.com&password=correct-horse'

# 3. Send it on every request.
curl http://127.0.0.1:8000/shipments -H 'Authorization: Bearer <token>'
```

In Swagger UI, use the **Authorize** button instead; it drives the same flow.

### What each role may do

| | Customer | Staff |
| --- | --- | --- |
| Book, amend and cancel shipments | Own only | Any |
| Read shipments and timelines | Own only | Any |
| Record a tracking scan | No | Yes |
| Read depots and handling labels | Yes | Yes |
| Create depots and handling labels | No | Yes |
| Browse the customer list | No | Yes |

Reading somebody else's shipment answers `404`, not `403`, so the API cannot be
used to discover which references exist. Being refused a staff-only route
answers `403`, because there the caller is known and the route is not a secret.

Roles are not settable at registration and there is no promotion endpoint;
staff are promoted directly in the database.

## Dashboard

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 proxies API calls to port 8000. Sign in as
`ada@example.com` / `correct-horse` after seeding.

## Project layout

```
app/
  main.py        # application instance and system routes
  api/
    deps.py      # authentication and role dependencies
    routers/     # one module per resource
  core/          # settings, password hashing, tokens
  db/            # engine and session factory
  models/        # SQLModel tables
  schemas/       # Pydantic request and response models
  services/      # carrier rate lookups, notifications
  seed.py        # demo dataset
  worker.py      # Celery application
alembic/         # migrations
frontend/        # React dashboard
tests/           # pytest suite
requirements.txt # pinned direct dependencies
```
