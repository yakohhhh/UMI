"""Stage 1-2: decode an uploaded session and check what protocol/README.md §3 requires of it."""

from dataclasses import dataclass

from umi_protocol import ProtocolError, Session, decode_session


class SessionRejected(ValueError):
    """The session cannot be processed; the message says why, for the uploader (HTTP 422)."""


@dataclass(frozen=True)
class Upload:
    """A decoded session that passed the upload checks: trimmed, complete, placed in time."""

    session: Session

    @property
    def device_id(self) -> str:
        return self.session.header.device_hex

    @property
    def session_id(self) -> int:
        return self.session.header.session_id


def read_upload(body: bytes, *, accept_simulated: bool) -> Upload:
    try:
        decoded = decode_session(body)
    except ProtocolError as exc:
        raise SessionRejected(f"Not a valid UMI v1 session log: {exc}") from exc
    header = decoded.header
    if not header.trimmed:
        # ADR 0006: an untrimmed trace is never stored, whatever client sent it.
        raise SessionRejected("The session is not trimmed: the phone removes the first and last 200 m before upload")
    if not decoded.complete:
        # The trim always writes END, so this upload was cut on the way. Storing it would make
        # the retry of the complete file a no-op (same device and session).
        raise SessionRejected(f"The session is incomplete ({decoded.issue}): upload the whole trimmed file")
    if header.simulated and not accept_simulated:
        raise SessionRejected("Sessions recorded with simulated sensors are not accepted here")
    session = Session(decoded)
    if session.time_sync is None:
        raise SessionRejected("The session has no TIME_SYNC record, so it cannot be placed in time")
    return Upload(session)
