"""Reading and writing session logs (``protocol/README.md`` §1).

Two levels:

* frames (``type``, ``len``, payload, CRC-16), read by :func:`read_frames` with their
  raw payload bytes, for code that must copy records untouched (the privacy trim);
* records, via :func:`decode_session`, :func:`encode_session` and the streaming
  :class:`SessionWriter`, for everything else.

A session cut short (no END, a record cut off or failing its CRC) decodes up to the
last good record and is reported incomplete. Bytes no correct writer produces raise
a :class:`~umi_protocol.errors.ProtocolError`.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .constants import FORMAT_MAX_RECORD_PAYLOAD, RecordType
from .crc import crc16_ccitt_false, crc32_iso_hdlc
from .errors import EncodeError, RecordError
from .records import RECORD_CLASSES, End, FixedRecord, Header, Record, UnknownRecord

#: ``type``, ``len`` and the CRC-16 around every payload.
FRAME_OVERHEAD = 4
_T_MS_SIZE = 4
_HEADER_LEN_OFFSET = 5
_HEADER_FLAGS = slice(6, 8)
_HEADER_CRC = slice(28, 32)


def encode_frame(record_type: int, payload: bytes) -> bytes:
    """One framed record: ``type``, ``len``, payload and its CRC-16."""
    if not 0 <= record_type <= 0xFF:
        raise EncodeError(f"record type {record_type} is not a u8")
    if not _T_MS_SIZE <= len(payload) <= FORMAT_MAX_RECORD_PAYLOAD:
        raise EncodeError(f"a payload holds {_T_MS_SIZE}..{FORMAT_MAX_RECORD_PAYLOAD} bytes, got {len(payload)}")
    body = bytes((record_type, len(payload))) + payload
    return body + crc16_ccitt_false(body).to_bytes(2, "little")


class _RecordOrder:
    """Ordering rules of §1.2 and §1.3, shared by the reader and the writer.

    ``t_ms`` never decreases; TRIM appears only as the first record of a session
    whose header has the ``trimmed`` flag, and such a session always starts with it.
    """

    def __init__(self, header: Header) -> None:
        self._trimmed = header.trimmed
        self.count = 0
        self.last_t_ms = 0

    def accept(self, record_type: int, t_ms: int) -> str | None:
        """Account for the next record (END included); returns the rule it breaks, if any."""
        if t_ms < self.last_t_ms:
            return f"t_ms {t_ms} is earlier than the previous record's {self.last_t_ms}"
        is_trim = record_type == RecordType.TRIM
        if is_trim and (self.count or not self._trimmed):
            return "TRIM is only allowed as the first record of a session with the trimmed flag"
        if self._trimmed and not self.count and not is_trim:
            return "a session with the trimmed flag must start with a TRIM record"
        if record_type != RecordType.END:
            self.count += 1
        self.last_t_ms = t_ms
        return None


# ---------------------------------------------------------------- reading


@dataclass(frozen=True, slots=True)
class Frame:
    """One record as stored: its type, raw payload and where it starts in the file."""

    offset: int
    type: int
    payload: bytes

    @property
    def t_ms(self) -> int:
        return int.from_bytes(self.payload[:_T_MS_SIZE], "little")

    def to_bytes(self) -> bytes:
        """The frame as stored (the CRC is a function of the rest, so this is the original)."""
        return encode_frame(self.type, self.payload)


@dataclass(frozen=True, slots=True)
class RawSession:
    """A session split into frames, payloads untouched. ``header_bytes`` includes any extension."""

    header: Header
    header_bytes: bytes
    frames: tuple[Frame, ...]
    end: End | None
    complete: bool
    issue: str | None


@dataclass(frozen=True, slots=True)
class DecodedSession:
    """A decoded session. ``records`` excludes END, which is in ``end`` when ``complete``.

    ``issue`` says why an incomplete session stops where it does.
    """

    header: Header
    records: tuple[Record, ...]
    complete: bool
    issue: str | None
    end: End | None


def read_frames(data: bytes) -> RawSession:
    """Split a session into frames, checking framing, CRCs, order and the END record."""
    header = Header.from_bytes(data)
    header_len = data[_HEADER_LEN_OFFSET]  # range-checked by Header.from_bytes
    order = _RecordOrder(header)
    frames: list[Frame] = []

    def cut_short(issue: str) -> RawSession:
        return RawSession(header, data[:header_len], tuple(frames), None, complete=False, issue=issue)

    pos = header_len
    while pos < len(data):
        if len(data) - pos < 2:
            return cut_short(f"record at byte {pos} is cut short")
        record_type, length = data[pos], data[pos + 1]
        crc_at = pos + 2 + length
        if crc_at + 2 > len(data):
            return cut_short(f"record at byte {pos} is cut short")
        if crc16_ccitt_false(data[pos:crc_at]) != int.from_bytes(data[crc_at : crc_at + 2], "little"):
            return cut_short(f"record at byte {pos} fails its CRC")
        if length < _T_MS_SIZE:
            raise RecordError(f"payload of {length} bytes has no t_ms", offset=pos)
        frame = Frame(pos, record_type, data[pos + 2 : crc_at])
        if (broken := order.accept(record_type, frame.t_ms)) is not None:
            raise RecordError(broken, offset=pos)
        if record_type == RecordType.END:
            end = _read_end(data, frame, record_count=len(frames))
            return RawSession(header, data[:header_len], tuple(frames), end, complete=True, issue=None)
        frames.append(frame)
        pos = crc_at + 2
    return cut_short("no END record")


def _check_size(cls: type[FixedRecord], frame: Frame) -> None:
    if len(frame.payload) < cls.LAYOUT.size:
        raise RecordError(
            f"{cls.TYPE.name} payload is {len(frame.payload)} bytes, v1 defines {cls.LAYOUT.size}", offset=frame.offset
        )


def _read_end(data: bytes, frame: Frame, *, record_count: int) -> End:
    _check_size(End, frame)
    end = End.from_payload(frame.payload)
    if end.record_count != record_count:
        raise RecordError(f"END counts {end.record_count} records, the session has {record_count}", offset=frame.offset)
    if end.file_crc32 != crc32_iso_hdlc(data[: frame.offset]):
        raise RecordError("END file_crc32 does not match the session", offset=frame.offset)
    if (after := frame.offset + len(frame.payload) + FRAME_OVERHEAD) != len(data):
        raise RecordError(f"{len(data) - after} bytes follow the END record", offset=after)
    return end


def parse_record(frame: Frame) -> Record:
    """The record a frame holds; types this reader does not know become :class:`UnknownRecord`."""
    if frame.type == RecordType.END:
        raise RecordError("END is only allowed as the last record", offset=frame.offset)
    cls = RECORD_CLASSES.get(frame.type)
    if cls is None:
        return UnknownRecord(frame.type, frame.payload)
    _check_size(cls, frame)
    return cls.from_payload(frame.payload)


def decode_session(data: bytes) -> DecodedSession:
    """Decode a whole session log."""
    raw = read_frames(data)
    records = tuple(parse_record(frame) for frame in raw.frames)
    return DecodedSession(raw.header, records, raw.complete, raw.issue, raw.end)


# ---------------------------------------------------------------- writing


class BinarySink(Protocol):
    """Where a :class:`SessionWriter` writes: a file opened in ``wb`` mode, a ``BytesIO``..."""

    def write(self, data: bytes, /) -> object: ...


class SessionWriter:
    """Appends records to a session log as they happen, the way the Clip does.

    The header is written at once. Each :meth:`append` writes one framed record, so
    the sink holds a readable (incomplete) session at all times; :meth:`finalize`
    writes the END record. A running CRC-32 means nothing is ever read back.
    """

    def __init__(self, sink: BinarySink, header: Header) -> None:
        self._sink = sink
        self._order = _RecordOrder(header)
        self._crc32 = 0
        self._finalized = False
        self._write(header.to_bytes())

    @property
    def record_count(self) -> int:
        return self._order.count

    @property
    def last_t_ms(self) -> int:
        return self._order.last_t_ms

    def append(self, record: Record) -> None:
        record_type = record.type if isinstance(record, UnknownRecord) else record.TYPE
        self.append_frame(record_type, record.to_payload())

    def append_frame(self, record_type: int, payload: bytes) -> None:
        """Append a raw payload, e.g. a known type carrying fields from a newer revision."""
        if self._finalized:
            raise EncodeError("the session is already finalized")
        if record_type == RecordType.END:
            raise EncodeError("END is written by finalize(), not appended")
        frame = encode_frame(record_type, payload)
        if (broken := self._order.accept(record_type, int.from_bytes(payload[:_T_MS_SIZE], "little"))) is not None:
            raise EncodeError(broken)
        self._write(frame)

    def finalize(self, duration_ms: int | None = None) -> End:
        """Write the END record. ``duration_ms`` defaults to the last record's ``t_ms``."""
        if self._finalized:
            raise EncodeError("the session is already finalized")
        t_ms = self._order.last_t_ms if duration_ms is None else duration_ms
        if (broken := self._order.accept(RecordType.END, t_ms)) is not None:
            raise EncodeError(broken)
        end = End(t_ms=t_ms, record_count=self._order.count, file_crc32=self._crc32)
        self._write(encode_frame(RecordType.END, end.to_payload()))
        self._finalized = True
        return end

    def _write(self, data: bytes) -> None:
        self._sink.write(data)
        self._crc32 = crc32_iso_hdlc(data, self._crc32)


def encode_session(
    header: Header, records: Iterable[Record], *, end: bool = True, duration_ms: int | None = None
) -> bytes:
    """Encode a whole session; ``end=False`` leaves it open, as after a power loss."""
    if not end and duration_ms is not None:
        raise EncodeError("duration_ms is the END record's t_ms; it needs end=True")
    buffer = io.BytesIO()
    writer = SessionWriter(buffer, header)
    for record in records:
        writer.append(record)
    if end:
        writer.finalize(duration_ms)
    return buffer.getvalue()


# ---------------------------------------------------------------- re-encoding (privacy trim)


def with_header_flags(header_bytes: bytes, header_flags: int) -> bytes:
    """Raw header bytes with new ``header_flags`` and a recomputed CRC, extension bytes kept."""
    body = bytearray(header_bytes[: _HEADER_CRC.start])
    body[_HEADER_FLAGS] = header_flags.to_bytes(2, "little")
    return bytes(body) + crc32_iso_hdlc(body).to_bytes(4, "little") + header_bytes[_HEADER_CRC.stop :]


def seal(preceding: bytes, *, record_count: int, t_ms: int) -> bytes:
    """``preceding`` (a header and its frames) followed by the END record that closes it."""
    end = End(t_ms=t_ms, record_count=record_count, file_crc32=crc32_iso_hdlc(preceding))
    return preceding + encode_frame(RecordType.END, end.to_payload())
