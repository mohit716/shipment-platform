import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.middleware import get_request_id

logger = logging.getLogger("fleetline.errors")


def error_body(message: str, *, details: list | None = None) -> dict:
    """One shape for every error the API returns.

    FastAPI's defaults disagree with each other: HTTPException produces
    {"detail": "..."} while a validation failure produces {"detail": [ ... ]}.
    A client then has to check whether detail is a string or a list before it
    can show anything, so both are normalised here into a message plus an
    optional list of field errors.

    The request id travels in the body as well as the header, because a user
    pasting a screenshot of an error is far more likely to include the body.
    """
    body = {"error": {"message": message, "request_id": get_request_id()}}
    if details:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Starlette's class rather than FastAPI's, because unmatched routes and
        # unsupported methods raise the Starlette one. Handling only FastAPI's
        # would leave 404s in the old shape.
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                # loc is a tuple like ("body", "weight_kg"); joined into a path
                # the dashboard can match against a form field name.
                "field": ".".join(str(part) for part in error["loc"][1:]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body("The request did not pass validation.", details=details),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Logged with the traceback and the request id, so the log has
        # everything and the response has nothing. An unhandled error's message
        # can name a table, a file path or a query, and none of that belongs in
        # a reply to whoever triggered it.
        logger.exception("unhandled error on %s %s", request.method, request.url.path)

        message = "Something went wrong on our side."
        if settings.debug:
            # In development the opposite is true: hiding the error means
            # switching to the terminal to find out what broke.
            message = f"{type(exc).__name__}: {exc}"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(message),
        )
