# Deploying FleetLine

The API is a FastAPI process in front of PostgreSQL. Redis and a Celery worker
are optional: with `CELERY_ENABLED=false` notifications run in-process.

Set `ENVIRONMENT=production`. The process will refuse to start if `SECRET_KEY`
is still a development placeholder, if `DEBUG` is true, or if SQL echo is on.

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Render

A small paid instance is enough for a demo. Use a Web Service for the API and
Render's managed PostgreSQL.

1. Create a PostgreSQL instance. Copy the internal URL and rewrite the scheme
   to `postgresql+asyncpg://` — asyncpg will not accept `postgres://`.
2. Create a Web Service from this repo.
   - Build: `pip install -r requirements.txt`
   - Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Environment variables:

| Variable | Value |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `DATABASE_ECHO` | `false` |
| `DATABASE_URL` | the rewritten asyncpg URL |
| `SECRET_KEY` | output of `token_urlsafe(32)` |
| `CORS_ORIGINS` | `["https://your-dashboard.onrender.com"]` |
| `FRONTEND_URL` | the dashboard origin |

4. Seed once: Render shell → `python -m app.seed`
5. The dashboard is a Static Site from `frontend/`. Build command `npm ci && npm run build`, publish directory `frontend/dist`. Point it at the API origin with a tiny `public/config.js` or rebuild with the API URL baked in via the nginx/static host you prefer. For a same-origin demo, skip the static site and put Caddy or nginx in front of both as Compose does.

Redis on Render is optional. Leave `CELERY_ENABLED=false` unless you add a
second Worker service running `celery -A app.worker.celery_app worker`.

## AWS

A first production-shaped layout on AWS:

| Piece | Service |
| --- | --- |
| API containers | ECS Fargate behind an Application Load Balancer |
| Images | ECR |
| Database | RDS PostgreSQL; `DATABASE_URL` from Secrets Manager |
| Broker | ElastiCache Redis if workers are on |
| Dashboard | S3 + CloudFront, or the same nginx image Compose uses |
| Secrets | Secrets Manager, injected as environment variables |
| CI | GitHub Actions builds and pushes the image on `main` |

The Dockerfile already runs migrations on boot. Run **one** API task during a
schema change, or an ECS one-shot task of `alembic upgrade head`, so two
tasks cannot race `alembic_version`.

Security groups: the ALB talks to the tasks on 8000; the tasks talk to RDS on
5432 and to Redis on 6379. Nothing else does.

Set `TRUST_PROXY_HEADERS=true` behind the ALB so rate limiting keys on the
client, not on the load balancer. Only do this when the proxy is the one
writing `X-Forwarded-For`.
