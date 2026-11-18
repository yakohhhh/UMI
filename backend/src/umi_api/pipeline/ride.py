"""Stage 4: the activity and its ride report (trace, 1 Hz samples, segments vs the street).

Distances and times cover the whole trip: the trimmed ends are added back from
the TRIM record (metres) and the session clock (seconds), the way a privacy zone
hides a trace without shortening the ride. The trace itself only has what was
uploaded.
"""

import itertools
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean
from typing import Self

from umi_protocol import Air

from umi_api.domain.aggregation import HourScores
from umi_api.domain.calendar import MADRID
from umi_api.domain.enums import ActivityType
from umi_api.domain.numbers import js_round, round_to
from umi_api.domain.scoring import (
    air_score_from_pm,
    comfort_score_from_vib,
    noise_score_from_db,
    pass_score,
    ride_safety_score,
)
from umi_api.pipeline.geometry import project, simplify
from umi_api.pipeline.matching import MatchedTrack, StreetIndex, StreetRun
from umi_api.pipeline.readings import Readings

# Douglas-Peucker tolerances of the ride report's trace and of the feed thumbnail.
ROUTE_TOLERANCE_M = 2.5
PREVIEW_TOLERANCE_M = 14.0
# A ride report charts at most this many samples (half an hour at 1 Hz); longer rides keep one fix in n.
MAX_REPORT_SAMPLES = 1800
# Fixes further apart than this were not ridden continuously (auto-pause, signal lost).
MAX_MOVING_GAP_MS = 5000
# Local hour a title part starts at.
_DAY_PARTS = ((22, "Night"), (18, "Evening"), (14, "Afternoon"), (11, "Lunch"), (5, "Morning"), (0, "Night"))
UNKNOWN_PLACE = "Barcelona"

type LngLatList = list[list[float]]


def activity_id(athlete_id: str, started_at: datetime) -> str:
    """Readable and stable: the rider and the local start minute, like the web mocks' ids."""
    return f"{athlete_id}-{started_at.astimezone(MADRID):%Y%m%d-%H%M}"


def title(activity: ActivityType, started_at: datetime) -> str:
    hour = started_at.astimezone(MADRID).hour
    part = next(name for start, name in _DAY_PARTS if hour >= start)
    return f"{part} {activity.value}"


@dataclass(frozen=True)
class ReportSampling:
    """Which track points the ride report charts: one every `step`."""

    step: int
    count: int

    @classmethod
    def for_points(cls, points: int) -> Self:
        step = -(-points // MAX_REPORT_SAMPLES)
        return cls(step=step, count=-(-points // step))

    def points(self) -> range:
        return range(0, self.step * self.count, self.step)

    def sample_of(self, point: int) -> int:
        """The report sample nearest to a track point."""
        return min(self.count - 1, js_round(point / self.step))


@dataclass(frozen=True)
class RideSummary:
    type: ActivityType
    title: str
    place: str
    started_at: datetime
    duration_s: int
    moving_time_s: int
    distance_m: int
    avg_speed_kmh: float
    max_speed_kmh: float
    scores: HourScores
    # Ambient temperature measured by the Clip (AIR records).
    temp_c: float
    preview: LngLatList
    route: LngLatList
    # [t (s), distance (m), speed (km/h), vibration (m/s² RMS), PM2.5 (µg/m³), noise (dB), route index]
    samples: list[list[float]]


@dataclass(frozen=True)
class SegmentRow:
    """A street segment the ride went through, scored for this pass and for the street at that hour."""

    position: int
    segment_id: str
    distance_m: int
    score: int
    street_average: int


def summarize(
    matched: MatchedTrack, readings: Readings, index: StreetIndex, sampling: ReportSampling, *, hard_brakes: int
) -> RideSummary:
    track = matched.track
    points = track.points
    trim = track.session.trim
    assert trim is not None, "read_upload() only accepts trimmed sessions"
    distance_m = js_round(trim.start_m + track.length_m + trim.end_m)
    duration_s = js_round(track.session.duration_ms / 1000)
    measured_moving_s = (
        sum(b.t_ms - a.t_ms for a, b in itertools.pairwise(points) if b.moving and b.t_ms - a.t_ms <= MAX_MOVING_GAP_MS)
        / 1000
    )
    # The trimmed ends are assumed ridden at the same pace as the rest.
    scale = distance_m / track.length_m if track.length_m > 0 else 1.0
    moving_time_s = min(duration_s, js_round(measured_moving_s * scale))
    route_kept = simplify([project(p.lon, p.lat) for p in points], ROUTE_TOLERANCE_M)
    route = [_lnglat(points[i].lon, points[i].lat) for i in route_kept]
    preview_kept = simplify([project(lon, lat) for lon, lat in route], PREVIEW_TOLERANCE_M)
    return RideSummary(
        type=track.activity,
        title=title(track.activity, track.started_at),
        place=_place(matched.runs, index),
        started_at=track.started_at,
        duration_s=max(duration_s, moving_time_s),
        moving_time_s=moving_time_s,
        distance_m=distance_m,
        avg_speed_kmh=round_to(distance_m / moving_time_s * 3.6, 1) if moving_time_s else 0.0,
        max_speed_kmh=round_to(max(p.speed_kmh for p in points), 1),
        scores=_scores(matched, readings, hard_brakes),
        temp_c=_temperature(track.session.of_type(Air)),
        preview=[route[i] for i in preview_kept],
        route=route,
        samples=[
            [
                round_to(points[i].t_ms / 1000, 1),
                js_round(trim.start_m + points[i].distance_m),
                round_to(points[i].speed_kmh, 1),
                round_to(readings.vib[i], 2),
                round_to(readings.pm25[i], 1),
                round_to(readings.db[i], 1),
                bisect_right(route_kept, i) - 1,
            ]
            for i in sampling.points()
        ],
    )


def segment_rows(matched: MatchedTrack, readings: Readings) -> list[SegmentRow]:
    rows = []
    for position, run in enumerate(matched.runs):
        street = readings.street[run.first]
        span = range(run.first, run.last + 1)
        comfort = _comfort(matched, readings, span)
        points = matched.track.points
        rows.append(
            SegmentRow(
                position=position,
                segment_id=run.segment_id,
                distance_m=js_round(points[run.last].distance_m - points[run.first].distance_m),
                score=pass_score(
                    comfort,
                    air_score_from_pm(fmean(readings.pm25[i] for i in span)),
                    noise_score_from_db(fmean(readings.db[i] for i in span)),
                ),
                street_average=pass_score(street.comfort, street.air, street.noise),
            )
        )
    return rows


def _scores(matched: MatchedTrack, readings: Readings, hard_brakes: int) -> HourScores:
    everywhere = range(len(matched.track.points))
    return HourScores(
        comfort=_comfort(matched, readings, everywhere),
        safety=ride_safety_score(fmean(s.safety for s in readings.street), hard_brakes),
        air=air_score_from_pm(fmean(readings.pm25)),
        noise=noise_score_from_db(fmean(readings.db)),
    )


def _comfort(matched: MatchedTrack, readings: Readings, span: Sequence[int]) -> int:
    """From the vibration felt while moving; a runner's IMU measures strides, so runs take the street's."""
    if matched.track.activity is ActivityType.RUN:
        return js_round(fmean(readings.street[i].comfort for i in span))
    points = matched.track.points
    moving = [readings.vib[i] for i in span if points[i].moving] or [readings.vib[i] for i in span]
    return comfort_score_from_vib(fmean(moving))


def _place(runs: Sequence[StreetRun], index: StreetIndex) -> str:
    """District where the ride started and where it ended, as the feed shows it ("Gràcia → Sant Martí")."""
    if not runs:
        return UNKNOWN_PLACE
    start, end = index.street(runs[0].segment_id).district, index.street(runs[-1].segment_id).district
    return start if start == end else f"{start} → {end}"


def _temperature(air: Sequence[Air]) -> float:
    # temp_cc has no "not available" value in v1 (protocol follow-up); 0 °C stands for no AIR record.
    return float(js_round(fmean(a.temp_c for a in air))) if air else 0.0


def _lnglat(lon: float, lat: float) -> list[float]:
    # 5 decimals is ~1 m, the precision of the GNSS fix.
    return [round_to(lon, 5), round_to(lat, 5)]
