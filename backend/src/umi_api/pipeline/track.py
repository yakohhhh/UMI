"""Stage 2: the plausible track, one point per GNSS fix with the sensor readings of that second.

Plausibility checks (domain.plausibility) either drop what cannot be believed or
refuse the whole session:

- refused: a session that ends in the future or is over a year old; no fix
  inside the service area; too many fixes faster than the activity allows (a car,
  a train). Timestamps going back are already refused by the decoder.
- dropped: fixes outside the service area, faster than the activity allows, or
  implying a jump from the previous fix beyond the GNSS error (multipath in a street canyon).
"""

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from statistics import median

from umi_protocol import Activity, Air, Sample, Session, haversine_m

from umi_api.domain.enums import ActivityType
from umi_api.domain.plausibility import (
    CLOCK_TOLERANCE,
    MAX_SESSION_AGE,
    MAX_SPEED_KMH,
    MAX_TOO_FAST_SHARE,
    RIDE_FROM_MEDIAN_KMH,
    in_service_area,
)
from umi_api.pipeline.upload import SessionRejected, Upload

# Below this speed the GNSS course over ground is noise.
HEADING_MIN_SPEED_KMH = 5.0
# Slower than this, the rider is standing.
MOVING_MIN_KMH = 2.0
# Two honest fixes a second apart can disagree by the GNSS error of both (a few metres each,
# more in a street canyon); a jump is a move beyond what the activity allows plus this.
JUMP_TOLERANCE_M = 20.0
# After this many fixes in a row rejected as jumps, the previous fix was the outlier: follow the new ones.
_MAX_JUMPS_IN_A_ROW = 3


@dataclass(frozen=True, slots=True)
class TrackPoint:
    """A fix the checks kept. Readings are None when the Clip had none (sensor off or not ready)."""

    t_ms: int
    lon: float
    lat: float
    speed_kmh: float
    # Course over ground, None when too slow to be meaningful.
    heading_deg: float | None
    vib_mps2: float | None
    noise_dba: float | None
    # From the last AIR record at or before the fix (the PM sensor reads every 10 s).
    pm25: float | None
    # Along the kept track, from its first point.
    distance_m: float

    @property
    def moving(self) -> bool:
        return self.speed_kmh >= MOVING_MIN_KMH


@dataclass(frozen=True)
class Track:
    upload: Upload
    activity: ActivityType
    points: tuple[TrackPoint, ...]
    # Fixes the plausibility checks removed.
    dropped: int

    @property
    def session(self) -> Session:
        return self.upload.session

    def utc(self, t_ms: int) -> datetime:
        instant = self.session.utc(t_ms)
        assert instant is not None, "read_upload() guarantees a TIME_SYNC"
        return instant

    @property
    def started_at(self) -> datetime:
        return self.utc(0)

    @property
    def length_m(self) -> float:
        return self.points[-1].distance_m

    @cached_property
    def _times(self) -> list[int]:
        return [p.t_ms for p in self.points]

    def nearest(self, t_ms: int) -> int:
        """Index of the point closest in time to `t_ms`."""
        times = self._times
        i = bisect_left(times, t_ms)
        if i == 0:
            return 0
        if i == len(times):
            return len(times) - 1
        return i if times[i] - t_ms < t_ms - times[i - 1] else i - 1


def build_track(upload: Upload, now: datetime) -> Track:
    session = upload.session
    ended_at = session.utc(session.duration_ms)
    assert ended_at is not None, "read_upload() guarantees a TIME_SYNC"
    if ended_at > now + CLOCK_TOLERANCE:
        raise SessionRejected(f"The session ends in the future ({ended_at:%Y-%m-%d %H:%M} UTC): check the Clip's clock")
    if ended_at < now - MAX_SESSION_AGE:
        raise SessionRejected("The session is more than a year old")

    fixes = [s for s in session.of_type(Sample) if s.has_fix]
    inside = [s for s in fixes if in_service_area(s.lon, s.lat)]
    if len(inside) < 2:
        raise SessionRejected("No position inside the service area (Barcelona)")
    activity = _activity(session.header.activity, inside)
    max_kmh = MAX_SPEED_KMH[activity]
    too_fast = sum(1 for s in inside if (s.speed_kmh or 0) > max_kmh)
    if too_fast > MAX_TOO_FAST_SHARE * len(inside):
        share = too_fast / len(inside)
        raise SessionRejected(f"{share:.0%} of the positions are faster than {max_kmh:g} km/h for a {activity}")

    kept = _without_glitches(inside, max_kmh)
    if len(kept) < 2:
        raise SessionRejected("Too few plausible positions to make a track")
    pm = _pm_at([s.t_ms for s, _ in kept], session.of_type(Air))
    points: list[TrackPoint] = []
    for (sample, speed), pm25 in zip(kept, pm, strict=True):
        distance = 0.0
        if points:
            prev = points[-1]
            distance = prev.distance_m + haversine_m(prev.lat, prev.lon, sample.lat, sample.lon)
        heading = sample.heading_deg if speed >= HEADING_MIN_SPEED_KMH else None
        points.append(
            TrackPoint(
                t_ms=sample.t_ms,
                lon=sample.lon,
                lat=sample.lat,
                speed_kmh=speed,
                heading_deg=heading if heading is not None and heading < 360 else None,
                vib_mps2=sample.vib_mps2,
                noise_dba=sample.noise_dba,
                pm25=pm25,
                distance_m=distance,
            )
        )
    return Track(upload=upload, activity=activity, points=tuple(points), dropped=len(fixes) - len(points))


def _activity(declared: Activity | int, fixes: Sequence[Sample]) -> ActivityType:
    """What the Clip says it recorded, or what its speed says when it did not know."""
    if declared == Activity.RIDE:
        return ActivityType.RIDE
    if declared == Activity.RUN:
        return ActivityType.RUN
    speeds = [s.speed_kmh for s in fixes if s.speed_kmh is not None and s.speed_kmh >= MOVING_MIN_KMH]
    return ActivityType.RIDE if speeds and median(speeds) >= RIDE_FROM_MEDIAN_KMH else ActivityType.RUN


def _without_glitches(fixes: Sequence[Sample], max_kmh: float) -> list[tuple[Sample, float]]:
    """Fixes worth keeping, each with its speed (GNSS, or implied by the move when the Clip had none)."""
    kept: list[tuple[Sample, float]] = []
    jumps = 0
    for sample in fixes:
        if sample.speed_kmh is not None and sample.speed_kmh > max_kmh:
            continue
        implied = 0.0
        if kept:
            prev = kept[-1][0]
            seconds = (sample.t_ms - prev.t_ms) / 1000
            if seconds <= 0:
                continue
            moved = haversine_m(prev.lat, prev.lon, sample.lat, sample.lon)
            if moved > max_kmh / 3.6 * seconds + JUMP_TOLERANCE_M and jumps < _MAX_JUMPS_IN_A_ROW:
                jumps += 1
                continue
            implied = moved / seconds * 3.6
        jumps = 0
        kept.append((sample, implied if sample.speed_kmh is None else sample.speed_kmh))
    return kept


def _pm_at(times: Sequence[int], air: Sequence[Air]) -> list[float | None]:
    """PM2.5 of the last AIR reading at or before each time."""
    readings = [(a.t_ms, a.pm25_ugm3) for a in air if a.pm25_ugm3 is not None]
    reading_times = [t for t, _ in readings]
    values: list[float | None] = []
    for t in times:
        i = bisect_right(reading_times, t)
        values.append(readings[i - 1][1] if i else None)
    return values
