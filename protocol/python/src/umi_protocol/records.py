"""The session header and every v1 record, as immutable values with their wire layout.

Field names and fixed-point units are exactly those of ``protocol/README.md`` §1:
the integers are what travels, and read-only properties convert them to SI units
(``Sample.speed_kmh``, ``Air.pm25_ugm3``...) without replacing them. Reserved bytes
are written as zero and ignored when reading.

Enum-valued fields hold the ``constants`` enum member when the value is known and
the plain integer otherwise: a newer Clip may add enum values within format v1, and
readers must keep them rather than fail.

Values are not range-checked on construction, only when encoded
(:meth:`FixedRecord.to_payload` raises :class:`~umi_protocol.errors.EncodeError`).
"""

from __future__ import annotations

import re
import struct
from dataclasses import Field, dataclass, fields
from enum import IntEnum, IntFlag
from typing import TYPE_CHECKING, Any, ClassVar, Self, get_args, get_type_hints

from .constants import (
    FORMAT_HDOP_UNKNOWN,
    FORMAT_HEADER_LEN,
    FORMAT_MAGIC,
    FORMAT_MAX_RECORD_PAYLOAD,
    FORMAT_NOT_AVAILABLE_U16,
    FORMAT_VERSION,
    SIGNING_SIGNATURE_LEN,
    Activity,
    EventKind,
    Fix,
    FlagSource,
    HazardKind,
    HeaderFlag,
    Lang,
    RecorderState,
    RecordType,
    SigAlg,
    StatusFlag,
)
from .crc import crc32_iso_hdlc
from .errors import EncodeError, HeaderError

#: Bytes 0–27 of a FLAG payload: what the Clip signs (§1.4).
FLAG_SIGNED_LEN = 28


type _EnumType = type[IntEnum] | type[IntFlag]


def _known(enum: _EnumType, value: int) -> int:
    """The enum member for ``value``, or ``value`` itself when this reader does not know it."""
    try:
        return enum(value)
    except ValueError:
        return value


def _measure(raw: int, scale: float) -> float | None:
    """SI value of an unsigned 16-bit measurement, ``None`` when the sensor had none."""
    return None if raw == FORMAT_NOT_AVAILABLE_U16 else raw * scale


_STRUCT_TOKEN = re.compile(r"(\d*)([xbBhHiIqQs])")


def _out_of_range(record: FixedRecord) -> EncodeError:
    """Name the first field that does not fit its wire type (struct only says which code failed)."""
    codes = [f"{count}{code}" if code == "s" else code for count, code in _STRUCT_TOKEN.findall(record.LAYOUT.format)]
    for (name, value), code in zip(record.wire_fields().items(), (c for c in codes if c != "x"), strict=True):
        try:
            struct.pack(f"<{code}", value)
        except struct.error:
            return EncodeError(f"{type(record).__name__}.{name} = {value!r} does not fit the wire type '{code}'")
    return EncodeError(f"{type(record).__name__} cannot be encoded")


class FixedRecord:
    """A record with a known v1 layout; subclasses are frozen dataclasses.

    ``LAYOUT`` lists the fields in dataclass order with ``x`` for reserved bytes,
    so packing and unpacking need no per-record code.
    """

    __slots__ = ()

    TYPE: ClassVar[RecordType]
    LAYOUT: ClassVar[struct.Struct]
    # Field names in wire order, with the enum of fields annotated `SomeEnum | int`.
    # Derived from the annotations once every record class exists (end of module).
    _SCHEMA: ClassVar[tuple[tuple[str, _EnumType | None], ...]]

    t_ms: int

    if TYPE_CHECKING:
        # Subclasses are dataclasses: these let mypy accept fields(cls) and cls(*values).
        __dataclass_fields__: ClassVar[dict[str, Field[Any]]]

        def __init__(self, *values: Any) -> None: ...

    def wire_fields(self) -> dict[str, int | bytes]:
        """Field name to wire value, in wire order (reserved bytes left out)."""
        return {name: getattr(self, name) for name, _ in self._SCHEMA}

    def to_payload(self) -> bytes:
        """The payload bytes as written on the wire; raises ``EncodeError`` on invalid values."""
        self._check()
        try:
            return self.LAYOUT.pack(*self.wire_fields().values())
        except struct.error:
            raise _out_of_range(self) from None

    @classmethod
    def from_payload(cls, payload: bytes) -> Self:
        """Decode a payload at least ``LAYOUT.size`` long; extra trailing bytes are ignored."""
        values = cls.LAYOUT.unpack_from(payload)
        return cls(*(v if enum is None else _known(enum, v) for (_, enum), v in zip(cls._SCHEMA, values, strict=True)))

    def _check(self) -> None:
        """Invariants beyond the wire types; overridden where a record has some."""


class _Positioned:
    """Degrees from the ``_e7`` fixed-point coordinates."""

    __slots__ = ()

    lat_e7: int
    lon_e7: int

    @property
    def lat(self) -> float:
        return self.lat_e7 / 1e7

    @property
    def lon(self) -> float:
        return self.lon_e7 / 1e7


@dataclass(frozen=True, slots=True, kw_only=True)
class Header:
    """The 32-byte session header (§1.1). ``format_version`` and ``header_len`` are implied."""

    header_flags: HeaderFlag | int = 0
    device_id: int
    session_id: int
    activity: Activity | int = Activity.UNKNOWN
    hw_rev: int = 0
    fw_version: tuple[int, int, int] = (0, 0, 0)

    # Everything up to the CRC; the 3 reserved bytes are the trailing pad.
    LAYOUT: ClassVar[struct.Struct] = struct.Struct("<4sBBHQIBB3B3x")
    SIZE: ClassVar[int] = FORMAT_HEADER_LEN

    @property
    def simulated(self) -> bool:
        return bool(self.header_flags & HeaderFlag.SIMULATED)

    @property
    def trimmed(self) -> bool:
        return bool(self.header_flags & HeaderFlag.TRIMMED)

    @property
    def device_hex(self) -> str:
        return format_device_id(self.device_id)

    def to_bytes(self) -> bytes:
        try:
            body = self.LAYOUT.pack(
                FORMAT_MAGIC.encode("ascii"),
                FORMAT_VERSION,
                self.SIZE,
                self.header_flags,
                self.device_id,
                self.session_id,
                self.activity,
                self.hw_rev,
                *self.fw_version,
            )
        except struct.error as exc:
            raise EncodeError(f"header value out of range: {exc}") from None
        return body + crc32_iso_hdlc(body).to_bytes(4, "little")

    @classmethod
    def from_bytes(cls, data: bytes) -> Header:
        """Parse and check the header at the start of ``data`` (which may hold the whole session).

        A ``header_len`` above 32 is accepted and its extra bytes are skipped: v1 lets
        the header grow. The CRC covers bytes 0–27 only, as specified.
        """
        if len(data) < cls.SIZE:
            raise HeaderError(f"a session starts with a {cls.SIZE}-byte header, got {len(data)} bytes")
        magic, version, header_len, flags, device_id, session_id, activity, hw_rev, *fw = cls.LAYOUT.unpack_from(data)
        if magic != FORMAT_MAGIC.encode("ascii"):
            raise HeaderError(f"bad magic {magic!r}, expected {FORMAT_MAGIC!r}")
        if version != FORMAT_VERSION:
            raise HeaderError(f"unsupported format_version {version}, this reader knows {FORMAT_VERSION}")
        if not cls.SIZE <= header_len <= len(data):
            raise HeaderError(f"header_len {header_len} is outside {cls.SIZE}..{len(data)}")
        stored = int.from_bytes(data[cls.LAYOUT.size : cls.SIZE], "little")
        if crc32_iso_hdlc(data[: cls.LAYOUT.size]) != stored:
            raise HeaderError("header CRC mismatch")
        return cls(
            header_flags=HeaderFlag(flags),
            device_id=device_id,
            session_id=session_id,
            activity=_known(Activity, activity),
            hw_rev=hw_rev,
            fw_version=(fw[0], fw[1], fw[2]),
        )


@dataclass(frozen=True, slots=True)
class Sample(FixedRecord, _Positioned):
    """SAMPLE (1): one per second while recording. Without a fix, position and motion are 0."""

    TYPE = RecordType.SAMPLE
    LAYOUT = struct.Struct("<IiiHHHHBBBx")

    t_ms: int
    lat_e7: int
    lon_e7: int
    speed_cms: int
    heading_cdeg: int
    vib_mms2: int
    noise_cdba: int
    hdop_d: int
    fix: Fix | int
    sats: int

    @property
    def has_fix(self) -> bool:
        # 1 is not a fix in v1 (NMEA GSA mode 1 means none); later values are better fixes.
        return self.fix >= Fix.TWO_D

    @property
    def speed_kmh(self) -> float | None:
        return _measure(self.speed_cms, 0.036)

    @property
    def heading_deg(self) -> float | None:
        return _measure(self.heading_cdeg, 0.01)

    @property
    def vib_mps2(self) -> float | None:
        return _measure(self.vib_mms2, 0.001)

    @property
    def noise_dba(self) -> float | None:
        return _measure(self.noise_cdba, 0.01)

    @property
    def hdop(self) -> float | None:
        return None if self.hdop_d == FORMAT_HDOP_UNKNOWN else self.hdop_d / 10


@dataclass(frozen=True, slots=True)
class Air(FixedRecord):
    """AIR (2): particulate matter and climate, every 10 s."""

    TYPE = RecordType.AIR
    LAYOUT = struct.Struct("<IHHHhH2x")

    t_ms: int
    pm1_dug: int
    pm25_dug: int
    pm10_dug: int
    temp_cc: int
    rh_dpct: int

    @property
    def pm1_ugm3(self) -> float | None:
        return _measure(self.pm1_dug, 0.1)

    @property
    def pm25_ugm3(self) -> float | None:
        return _measure(self.pm25_dug, 0.1)

    @property
    def pm10_ugm3(self) -> float | None:
        return _measure(self.pm10_dug, 0.1)

    @property
    def temp_c(self) -> float:
        return self.temp_cc / 100

    @property
    def rh_pct(self) -> float | None:
        return _measure(self.rh_dpct, 0.1)


@dataclass(frozen=True, slots=True)
class Event(FixedRecord, _Positioned):
    """EVENT (3): a hard brake or a pothole detected on the Clip."""

    TYPE = RecordType.EVENT
    LAYOUT = struct.Struct("<IBxHHHii")

    t_ms: int
    kind: EventKind | int
    value_mms2: int
    peak_mms2: int
    duration_ms: int
    lat_e7: int
    lon_e7: int

    @property
    def value_mps2(self) -> float | None:
        return _measure(self.value_mms2, 0.001)

    @property
    def peak_mps2(self) -> float | None:
        return _measure(self.peak_mms2, 0.001)


@dataclass(frozen=True, slots=True)
class Flag(FixedRecord, _Positioned):
    """FLAG (4): the rider pressed the button. Bytes 0–27 are signed by the Clip (§1.4)."""

    TYPE = RecordType.FLAG
    LAYOUT = struct.Struct(f"<IHBBBB2xiiHHH2xBB{SIGNING_SIGNATURE_LEN}s")

    t_ms: int
    seq: int
    source: FlagSource | int
    kind: HazardKind | int
    confidence: int
    lang: Lang | int
    lat_e7: int
    lon_e7: int
    speed_cms: int
    vib_mms2: int
    noise_cdba: int
    sig_alg: SigAlg | int = SigAlg.NONE
    sig_len: int = 0
    signature: bytes = bytes(SIGNING_SIGNATURE_LEN)

    @property
    def is_signed(self) -> bool:
        return self.sig_alg != SigAlg.NONE

    @property
    def signed_payload(self) -> bytes:
        """Payload bytes 0–27, the part covered by the signature."""
        return self.to_payload()[:FLAG_SIGNED_LEN]

    @property
    def speed_kmh(self) -> float | None:
        return _measure(self.speed_cms, 0.036)

    @property
    def vib_mps2(self) -> float | None:
        return _measure(self.vib_mms2, 0.001)

    @property
    def noise_dba(self) -> float | None:
        return _measure(self.noise_cdba, 0.01)

    def _check(self) -> None:
        if len(self.signature) != SIGNING_SIGNATURE_LEN:
            raise EncodeError(f"Flag.signature must be {SIGNING_SIGNATURE_LEN} bytes, got {len(self.signature)}")
        if self.sig_alg == SigAlg.NONE:
            if self.sig_len != 0 or any(self.signature):
                raise EncodeError("an unsigned Flag has sig_len 0 and a zero-filled signature")
        elif self.sig_len != SIGNING_SIGNATURE_LEN:
            raise EncodeError(f"a signed Flag has sig_len {SIGNING_SIGNATURE_LEN}, got {self.sig_len}")


@dataclass(frozen=True, slots=True)
class FlagUndo(FixedRecord):
    """FLAG_UNDO (5): a double press cancelled the flag with this ``seq``."""

    TYPE = RecordType.FLAG_UNDO
    LAYOUT = struct.Struct("<IH")

    t_ms: int
    seq: int


@dataclass(frozen=True, slots=True)
class Status(FixedRecord):
    """STATUS (6): battery, board and storage health, every 60 s."""

    TYPE = RecordType.STATUS
    LAYOUT = struct.Struct("<IBBHhH")

    t_ms: int
    battery_pct: int
    flags: StatusFlag | int
    battery_mv: int
    board_temp_cc: int
    free_kib: int

    @property
    def battery_v(self) -> float | None:
        return _measure(self.battery_mv, 0.001)

    @property
    def board_temp_c(self) -> float:
        return self.board_temp_cc / 100


@dataclass(frozen=True, slots=True)
class TimeSync(FixedRecord):
    """TIME_SYNC (7): ties the session clock to UTC; the first one places the session in time."""

    TYPE = RecordType.TIME_SYNC
    LAYOUT = struct.Struct("<Iq")

    t_ms: int
    unix_ms: int


@dataclass(frozen=True, slots=True)
class State(FixedRecord):
    """STATE (8): the recorder started, auto-paused or resumed."""

    TYPE = RecordType.STATE
    LAYOUT = struct.Struct("<IBx")

    t_ms: int
    state: RecorderState | int


@dataclass(frozen=True, slots=True)
class Trim(FixedRecord):
    """TRIM (9): written by the phone right after the header; metres removed at each end."""

    TYPE = RecordType.TRIM
    LAYOUT = struct.Struct("<IHH")

    t_ms: int
    start_m: int
    end_m: int


@dataclass(frozen=True, slots=True)
class End(FixedRecord):
    """END (127): closes a complete session. Computed by the encoder, never built by hand."""

    TYPE = RecordType.END
    LAYOUT = struct.Struct("<II4xI")

    t_ms: int
    record_count: int
    file_crc32: int


@dataclass(frozen=True, slots=True)
class UnknownRecord:
    """A record type this reader does not know, kept as is (forward compatibility)."""

    type: int
    payload: bytes

    @property
    def t_ms(self) -> int:
        return int.from_bytes(self.payload[:4], "little")

    def to_payload(self) -> bytes:
        if self.type in _KNOWN_TYPES or not 0 <= self.type <= 0xFF:
            raise EncodeError(f"UnknownRecord.type {self.type} must be an unassigned u8 record type")
        if not 4 <= len(self.payload) <= FORMAT_MAX_RECORD_PAYLOAD:
            raise EncodeError(f"a payload holds 4..{FORMAT_MAX_RECORD_PAYLOAD} bytes, got {len(self.payload)}")
        return self.payload


type KnownRecord = Sample | Air | Event | Flag | FlagUndo | Status | TimeSync | State | Trim
"""A record this reader decodes into fields (END aside, which closes the session)."""

type Record = KnownRecord | UnknownRecord
"""Anything a session holds between its header and its END."""

_RECORD_CLASSES: tuple[type[KnownRecord], ...] = (Sample, Air, Event, Flag, FlagUndo, Status, TimeSync, State, Trim)

#: Record class for each known record type, END excluded.
RECORD_CLASSES: dict[int, type[KnownRecord]] = {cls.TYPE: cls for cls in _RECORD_CLASSES}

_KNOWN_TYPES = frozenset({*RECORD_CLASSES, End.TYPE})


def _schema(cls: type[FixedRecord]) -> tuple[tuple[str, _EnumType | None], ...]:
    hints = get_type_hints(cls)
    enums = {f.name: next((a for a in get_args(hints[f.name]) if _is_enum(a)), None) for f in fields(cls)}
    return tuple(enums.items())


def _is_enum(hint: object) -> bool:
    return isinstance(hint, type) and issubclass(hint, IntEnum | IntFlag)


for _cls in (*_RECORD_CLASSES, End):
    _cls._SCHEMA = _schema(_cls)


def format_device_id(device_id: int) -> str:
    """``device_id`` as shown everywhere: 16 lowercase hex digits."""
    return f"{device_id:016x}"


def parse_device_id(text: str) -> int:
    """Inverse of :func:`format_device_id`; accepts an optional ``0x`` prefix."""
    value = int(text.removeprefix("0x"), 16)
    if not 0 <= value < 1 << 64:
        raise ValueError(f"device_id {text!r} is not a u64")
    return value
