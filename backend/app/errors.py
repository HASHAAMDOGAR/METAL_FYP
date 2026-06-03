"""Error envelope and exception handlers (spec §8.2)."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    """Raised by services/routers to produce a consistent error envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _envelope(code: str, message: str, details: Any | None = None) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


# Convenience constructors -------------------------------------------------
def not_found(message: str = "Resource not found", code: str = "not_found") -> APIError:
    return APIError(status.HTTP_404_NOT_FOUND, code, message)


def conflict(message: str, code: str = "conflict", details: Any | None = None) -> APIError:
    return APIError(status.HTTP_409_CONFLICT, code, message, details)


def forbidden(message: str = "Forbidden", code: str = "forbidden") -> APIError:
    return APIError(status.HTTP_403_FORBIDDEN, code, message)


def unauthorized(message: str = "Not authenticated", code: str = "unauthorized") -> APIError:
    return APIError(status.HTTP_401_UNAUTHORIZED, code, message)


def bad_request(message: str, code: str = "bad_request", details: Any | None = None) -> APIError:
    return APIError(status.HTTP_400_BAD_REQUEST, code, message, details)


def unsupported_media(message: str, code: str = "unsupported_format") -> APIError:
    return APIError(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, code, message)


def service_unavailable(message: str, code: str = "service_unavailable") -> APIError:
    return APIError(status.HTTP_503_SERVICE_UNAVAILABLE, code, message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("validation_error", "Request validation failed", exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail)),
        )
