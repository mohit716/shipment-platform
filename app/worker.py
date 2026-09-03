from celery import Celery

from app.core.config import settings

# The worker is a separate process from the API. It imports the same settings
# and the same services, but it never imports app.main: a worker that pulls in
# the whole ASGI application would start needing web dependencies to run a task.
celery_app = Celery(
    "fleetline",
    broker=settings.celery_broker_url,
    # Where results are stored. Both point at Redis here, but they are separate
    # settings because they are separate jobs: the broker delivers work, the
    # backend keeps answers.
    backend=settings.celery_result_backend,
    include=["app.tasks.notifications"],
)

celery_app.conf.update(
    # JSON rather than pickle. Pickle can execute arbitrary code on
    # deserialisation, so a broker anyone can write to becomes a way to run code
    # in the worker.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # A task that hangs on an unreachable SMTP server should be killed rather
    # than holding a worker slot indefinitely.
    task_time_limit=60,
    task_soft_time_limit=45,
    # Acknowledge after the task finishes, not when it is picked up. If a worker
    # dies mid-task the message returns to the queue instead of vanishing.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
