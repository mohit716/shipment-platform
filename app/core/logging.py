import logging
import sys

from app.core.middleware import RequestIdFilter

# request_id comes from the filter, not the call site, so every line carries it
# without a single logger.info having to pass it along.
FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Send application logs to stdout in one consistent format.

    stdout rather than a file, because in a container the platform collects the
    stream. Writing to a file means the logs live inside a filesystem that
    disappears when the container is replaced.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    # Replace rather than append. Reloading in development would otherwise stack
    # handlers and print every line two or three times.
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn installs its own access log in a different format and without the
    # request id. The middleware already logs every request, so this one is
    # silenced rather than duplicated.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
