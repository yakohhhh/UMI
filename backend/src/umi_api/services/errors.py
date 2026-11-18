"""Failures a use case can report; the API layer maps them to HTTP statuses."""


class ServiceError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(ServiceError):
    pass


class ForbiddenError(ServiceError):
    pass


class ConflictError(ServiceError):
    """The request is valid but the resource is not in a state that allows it."""


class UnprocessableError(ServiceError):
    """Well-formed, but the content cannot be accepted (an invalid or refused session log, a bad key)."""


class UnavailableError(ServiceError):
    """Something the use case needs is not there yet (e.g. the street network before the first seed)."""
