"""Stage 7: segment passes, the unit street scores are recomputed from (domain.aggregation).

One row per street segment and hour the pass began in: runs on the same segment
that began in the same hour (a loop) merge into one pass. Hours are UTC hour
starts, which are also Barcelona hour starts (whole-hour offset); aggregation
reads them in local time.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean

from umi_api.domain.enums import ActivityType
from umi_api.domain.reports import brake_weight
from umi_api.pipeline.matching import MatchedTrack, StreetRun
from umi_api.pipeline.readings import DB, PM25, VIB, Readings
from umi_api.pipeline.track import Track

# (segment id, hour start): what makes a pass unique within an activity.
type PassKey = tuple[str, datetime]


@dataclass(frozen=True)
class PassRow:
    segment_id: str
    hour_start: datetime
    # Ride passes only: a runner's IMU measures strides, not the surface.
    vib_rms: float | None
    pm25: float | None
    db: float | None
    hard_brakes: int
    # Brakes weighted by what riders said about them; nothing is answered yet at ingest.
    weighted_brakes: float

    @property
    def key(self) -> PassKey:
        return self.segment_id, self.hour_start


def pass_key(track: Track, run: StreetRun) -> PassKey:
    start = track.utc(track.points[run.first].t_ms)
    return run.segment_id, start.replace(minute=0, second=0, microsecond=0)


def segment_passes(matched: MatchedTrack, readings: Readings, brake_points: Sequence[int]) -> list[PassRow]:
    """`brake_points`: the track points the ride's hard brakes are drawn at."""
    track = matched.track
    groups: dict[PassKey, list[StreetRun]] = defaultdict(list)
    for run in matched.runs:
        groups[pass_key(track, run)].append(run)
    ride = track.activity is ActivityType.RIDE
    rows = []
    for (segment_id, hour_start), runs in groups.items():
        span = [i for run in runs for i in range(run.first, run.last + 1)]
        moving = [i for i in span if track.points[i].moving] or span
        braked = sum(1 for point in brake_points if any(point in run for run in runs))
        rows.append(
            PassRow(
                segment_id=segment_id,
                hour_start=hour_start,
                vib_rms=fmean(readings.vib[i] for i in moving) if ride and VIB in readings.measured else None,
                pm25=fmean(readings.pm25[i] for i in span) if PM25 in readings.measured else None,
                db=fmean(readings.db[i] for i in span) if DB in readings.measured else None,
                hard_brakes=braked,
                weighted_brakes=braked * brake_weight(None),
            )
        )
    return rows
