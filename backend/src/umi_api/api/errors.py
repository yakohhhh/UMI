"""Use-case failures as JSON, in FastAPI's `{"detail": ...}` shape."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from umi_api.services.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    UnavailableError,
    UnprocessableError,
)

_STATUS: dict[type[ServiceError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    ConflictError: status.HTTP_409_CONFLICT,
    UnprocessableError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    UnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


async def _service_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ServiceError)
    code = next((code for kind, code in _STATUS.items() if isinstance(exc, kind)), status.HTTP_400_BAD_REQUEST)
    return JSONResponse(status_code=code, content={"detail": exc.detail})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, _service_error)
