"""The privacy trim (``protocol/README.md`` §2): reference implementation.

The phone runs it before any upload; the mobile app must produce the same bytes on
the golden vectors. Records are removed, never rewritten: kept frames are copied
byte for byte, so the Clip's flag signatures still verify afterwards.

Trimming is not idempotent and is refused on a session that already has the
``trimmed`` flag: a second pass would cut another 200 m from each end and its TRIM
record could no longer say how much of the original trip was removed.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .codec import Frame, encode_frame, parse_record, read_frames, seal, with_header_flags
from .constants import PRIVACY_MIN_UPLOAD_DISTANCE_M, PRIVACY_TRIM_M, HeaderFlag, RecordType
from .errors import TrimError
from .records import Flag, FlagUndo, Record, Status, TimeSync, Trim
from .session import PathPoint, path_of

_U16_MAX = 0xFFFF


@dataclass(frozen=True, slots=True)
class TrimWindow:
    """Records with ``t_start <= t_ms <= t_end`` are kept; ``*_m`` are the metres cut at each end."""

    t_start: int
    t_end: int
    start_m: int
    end_m: int

    def __contains__(self, t_ms: int) -> bool:
        return self.t_start <= t_ms <= self.t_end


@dataclass(frozen=True, slots=True)
class TrimResult:
    """Outcome of :func:`trim_session`.

    ``data`` is the session to upload, or ``None`` when nothing may be uploaded
    (``reason`` says why; ``start_m``, ``end_m`` and ``dropped`` are then empty).
    ``dropped`` counts removed records per record type.
    """

    data: bytes | None
    total_m: float
    start_m: int = 0
    end_m: int = 0
    dropped: Mapping[int, int] = field(default_factory=dict)
    reason: str | None = None


def _whole_metres(distance_m: float) -> int:
    # Floor rather than round: no rounding mode to agree on between languages.
    return min(math.floor(distance_m), _U16_MAX)


def plan_trim(path: Sequence[PathPoint]) -> TrimWindow | None:
    """Where to cut a path, or ``None`` when the session must not be uploaded at all.

    ``None`` means the path is shorter than ``min_upload_distance_m``, or no sample is
    at least ``trim_m`` from both ends (sparse fixes): nothing would be left.
    """
    if not path or (total := path[-1].distance_m) < PRIVACY_MIN_UPLOAD_DISTANCE_M:
        return None
    # Both exist: the first point is 0 m from the start and the last is `total` from it.
    first = next(i for i, p in enumerate(path) if p.distance_m >= PRIVACY_TRIM_M)
    last = next(i for i in reversed(range(len(path))) if total - path[i].distance_m >= PRIVACY_TRIM_M)
    if first > last:
        return None
    return TrimWindow(
        t_start=path[first].t_ms,
        t_end=path[last].t_ms,
        start_m=_whole_metres(path[first].distance_m),
        end_m=_whole_metres(total - path[last].distance_m),
    )


def _kept(record: Record, window: TrimWindow, kept_flags: set[int]) -> bool:
    if isinstance(record, TimeSync | Status):
        return True
    if isinstance(record, FlagUndo):
        # A FLAG_UNDO has no position; dropping it while its flag stays would revive
        # a flag the rider cancelled.
        return record.t_ms in window or record.seq in kept_flags
    # Telemetry, flags, states, and record types this reader does not know: a newer
    # record may carry a position, so it is cut like the rest of the trace.
    return record.t_ms in window


def trim_session(data: bytes) -> TrimResult:
    """Trim a session for upload. Sessions cut short are accepted and come out complete."""
    raw = read_frames(data)
    if raw.header.trimmed:
        raise TrimError("the session is already trimmed")
    records = [parse_record(frame) for frame in raw.frames]
    path = path_of(records)
    total_m = path[-1].distance_m if path else 0.0
    window = plan_trim(path)
    if window is None:
        if total_m < PRIVACY_MIN_UPLOAD_DISTANCE_M:
            reason = f"the trip is {total_m:.0f} m, under the {PRIVACY_MIN_UPLOAD_DISTANCE_M} m minimum"
        else:
            reason = f"no sample is {PRIVACY_TRIM_M} m or more from both ends of the trip"
        return TrimResult(data=None, total_m=total_m, reason=reason)

    kept_flags = {r.seq for r in records if isinstance(r, Flag) and r.t_ms in window}
    kept: list[Frame] = []
    dropped: Counter[int] = Counter()
    for frame, record in zip(raw.frames, records, strict=True):
        if _kept(record, window, kept_flags):
            kept.append(frame)
        else:
            dropped[RecordType(frame.type) if frame.type in RecordType else frame.type] += 1

    trim = Trim(t_ms=0, start_m=window.start_m, end_m=window.end_m)
    body = b"".join(
        (
            with_header_flags(raw.header_bytes, raw.header.header_flags | HeaderFlag.TRIMMED),
            encode_frame(RecordType.TRIM, trim.to_payload()),
            *(frame.to_bytes() for frame in kept),
        )
    )
    # END keeps the original duration; a session cut short ends at its last record
    # (there is one: the window was found on its samples).
    duration_ms = raw.end.t_ms if raw.end is not None else raw.frames[-1].t_ms
    return TrimResult(
        data=seal(body, record_count=1 + len(kept), t_ms=duration_ms),
        total_m=total_m,
        start_m=window.start_m,
        end_m=window.end_m,
        dropped=dict(dropped),
    )
