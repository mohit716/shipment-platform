import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger("fleetline.access")

# A ContextVar rather than a module-level global. Under async concurrency many
# requests are in flight in the same thread, and a plain global would be
# overwritten by whichever one ran most recently. Each task gets its own view of
# a ContextVar, so a log line written deep inside a handler still reports the id
# of the request that is actually running.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Gives every request an id and records how long it took.

    Middleware rather than a dependency, because it has to wrap responses the
    routes never produce: 404s for unmatched paths, 422s raised during
    validation, and anything a later exception handler turns into a response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # An incoming id is honoured so a trace started at a load balancer or by
        # the dashboard carries through, rather than being renamed at every hop.
        incoming = request.headers.get("X-Request-ID")
        request_id = incoming or uuid.uuid4().hex
        token = request_id_var.set(request_id)

        # perf_counter, not time(): it is monotonic, so a clock adjustment
        # cannot produce a negative duration.
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        duration_ms = (time.perf_counter() - started) * 1000

        # Echoed back so a user reporting a problem can quote the id from their
        # network tab and it can be found in the logs.
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = f"{duration_ms:.1f}"

        logger.info(
            '%s %s %s %.1fms request_id=%s',
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response


def get_request_id() -> str:
    """The id of the request currently being served, or "-" outside one."""
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    """Puts the request id on every log record.

    A filter rather than a formatter, so the id is available to any handler and
    any format string without every logger having to pass it explicitly.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True
