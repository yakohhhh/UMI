"""What each track point measured and what its street is usually like at that hour."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from umi_api.domain.aggregation import HourScores
from umi_api.domain.calendar import local_hour
from umi_api.pipeline.matching import MatchedTrack, StreetIndex, Typical


@dataclass(frozen=True)
class Readings:
    """Aligned with the track points.

    A reading the Clip did not have holds the previous one (the first one, before
    it). A sensor that was off for the whole session (riders can disable sensors)
    reads as the matched street's typical value: the ride report needs a number,
    and the street's is the best estimate.
    """

    vib: tuple[float, ...]
    pm25: tuple[float, ...]
    db: tuple[float, ...]
    # The street's published scores at the point's local hour (typical ones off the network).
    street: tuple[HourScores, ...]
    # Channels the Clip measured at least once; the others are street estimates, never fed
    # back into street scores.
    measured: frozenset[str]


VIB, PM25, DB = "vib", "pm25", "db"


def readings(matched: MatchedTrack, index: StreetIndex, hourly: Mapping[str, Sequence[HourScores]]) -> Readings:
    points = matched.track.points
    typical = [_typical(index, sid) for sid in matched.segment_ids]
    street = []
    for point, sid, usual in zip(points, matched.segment_ids, typical, strict=True):
        by_hour = hourly.get(sid) if sid is not None else None
        street.append(by_hour[local_hour(matched.track.utc(point.t_ms))] if by_hour else usual.scores)
    channels = {
        VIB: [p.vib_mps2 for p in points],
        PM25: [p.pm25 for p in points],
        DB: [p.noise_dba for p in points],
    }
    return Readings(
        vib=_filled(channels[VIB], [t.vib_rms for t in typical]),
        pm25=_filled(channels[PM25], [t.pm25 for t in typical]),
        db=_filled(channels[DB], [t.db for t in typical]),
        street=tuple(street),
        measured=frozenset(name for name, values in channels.items() if any(v is not None for v in values)),
    )


def _typical(index: StreetIndex, segment_id: str | None) -> Typical:
    return index.city_typical if segment_id is None else index.street(segment_id).typical


def _filled(measured: Sequence[float | None], fallback: Sequence[float]) -> tuple[float, ...]:
    first = next((v for v in measured if v is not None), None)
    if first is None:
        return tuple(fallback)
    values, last = [], first
    for value in measured:
        if value is not None:
            last = value
        values.append(last)
    return tuple(values)
