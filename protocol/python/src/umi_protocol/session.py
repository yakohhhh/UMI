"""A read view over a decoded session: absolute time, path, effective flags.

These are the interpretation rules of ``protocol/README.md`` §1.3 in one place, so
the backend, the simulator and the CLI cannot each read a session differently.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cached_property

from .codec import DecodedSession, decode_session
from .geo import haversine_m
from .records import Flag, FlagUndo, Header, Record, Sample, TimeSync, Trim

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def utc_from_unix_ms(unix_ms: int) -> datetime:
    """Exact UTC datetime of a Unix time in milliseconds (no float rounding)."""
    return _EPOCH + timedelta(milliseconds=unix_ms)


@dataclass(frozen=True, slots=True)
class PathPoint:
    """A SAMPLE with a fix and the distance travelled to it from the first one."""

    sample: Sample
    distance_m: float

    @property
    def t_ms(self) -> int:
        return self.sample.t_ms


def path_of(records: Iterable[Record]) -> tuple[PathPoint, ...]:
    """Cumulative haversine distance along the SAMPLE records that have a fix.

    Samples without a fix are skipped, not treated as a break: the path joins the
    fixes on either side of a gap.
    """
    points: list[PathPoint] = []
    for record in records:
        if not isinstance(record, Sample) or not record.has_fix:
            continue
        if points:
            prev = points[-1]
            step = haversine_m(prev.sample.lat, prev.sample.lon, record.lat, record.lon)
            points.append(PathPoint(record, prev.distance_m + step))
        else:
            points.append(PathPoint(record, 0.0))
    return tuple(points)


def effective_flags(records: Iterable[Record]) -> tuple[Flag, ...]:
    """FLAG records not cancelled by a FLAG_UNDO with their ``seq``, in session order."""
    records = tuple(records)
    undone = {r.seq for r in records if isinstance(r, FlagUndo)}
    return tuple(r for r in records if isinstance(r, Flag) and r.seq not in undone)


class Session:
    """Derived views of a :class:`~umi_protocol.codec.DecodedSession`, computed on first use."""

    def __init__(self, decoded: DecodedSession) -> None:
        self.decoded = decoded

    @classmethod
    def from_bytes(cls, data: bytes) -> Session:
        return cls(decode_session(data))

    @property
    def header(self) -> Header:
        return self.decoded.header

    @property
    def records(self) -> tuple[Record, ...]:
        return self.decoded.records

    def of_type[R](self, cls: type[R]) -> tuple[R, ...]:
        """Every record of one class, in session order."""
        return tuple(r for r in self.decoded.records if isinstance(r, cls))

    @cached_property
    def time_sync(self) -> TimeSync | None:
        """The first TIME_SYNC: the only one used to place records in time."""
        return next(iter(self.of_type(TimeSync)), None)

    def unix_ms(self, t_ms: int) -> int | None:
        """Absolute time of a session time ``t_ms``, ``None`` without a TIME_SYNC."""
        sync = self.time_sync
        return None if sync is None else sync.unix_ms - sync.t_ms + t_ms

    def utc(self, t_ms: int) -> datetime | None:
        unix_ms = self.unix_ms(t_ms)
        return None if unix_ms is None else utc_from_unix_ms(unix_ms)

    @property
    def started_at(self) -> datetime | None:
        return self.utc(0)

    @property
    def duration_ms(self) -> int:
        """END's ``t_ms``, or the last record's for a session cut short."""
        if self.decoded.end is not None:
            return self.decoded.end.t_ms
        return self.decoded.records[-1].t_ms if self.decoded.records else 0

    @property
    def trim(self) -> Trim | None:
        """The TRIM record of a session the phone trimmed."""
        return next(iter(self.of_type(Trim)), None)

    @cached_property
    def path(self) -> tuple[PathPoint, ...]:
        return path_of(self.decoded.records)

    @property
    def distance_m(self) -> float:
        return self.path[-1].distance_m if self.path else 0.0

    @cached_property
    def flags(self) -> tuple[Flag, ...]:
        """Flags the rider kept: FLAG records minus those undone by a double press."""
        return effective_flags(self.decoded.records)
