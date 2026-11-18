"""Exceptions raised when bytes or values do not follow UMI protocol v1.

A session cut short (power loss, bad CRC) is *not* an error: the decoder returns
what it could read and marks the session incomplete. These exceptions are for data
that no correct writer produces, so callers can refuse it outright.
"""

from __future__ import annotations


class ProtocolError(ValueError):
    """Base class for every protocol violation."""

    def __init__(self, message: str, *, offset: int | None = None) -> None:
        super().__init__(message if offset is None else f"{message} (at byte {offset})")
        self.offset = offset


class HeaderError(ProtocolError):
    """The 32-byte session header is missing, corrupt or of an unsupported version."""


class RecordError(ProtocolError):
    """A record with a valid CRC breaks the format (too short, out of order, END mismatch...)."""


class EncodeError(ProtocolError):
    """Values that cannot be written as a valid session (out of range, wrong order...)."""


class TrimError(ProtocolError):
    """The privacy trim cannot run on this session."""
