# API image. Worker and beat reuse it with a different command.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 1000 fleetline

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini alembic.ini
COPY alembic alembic
COPY app app

USER fleetline
EXPOSE 8000

# Migrations run first so a new container never serves against an old schema.
# exec replaces the shell so signals reach uvicorn rather than dying at sh.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
