"""Stage 3: map matching, which street segment each fix of the track was on.

Street segments are short polylines (most are one straight Cerdà block). Their
edges sit in an in-memory grid, so the edges within reach of a fix are found in
constant time (ADR 0004: PostGIS is not worth it at ~335 segments). A fix goes
to the nearest edge within `MAX_DISTANCE_M` whose axis agrees with the rider's
course, staying on the current segment when it is nearly as close, so crossing a
junction does not flicker onto the cross street. Blips of one or two fixes on
another segment between two runs of the same one are smoothed away.
"""

import itertools
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cached_property
from statistics import fmean

from umi_api.domain.aggregation import HourScores
from umi_api.domain.numbers import js_round
from umi_api.pipeline.geometry import XY, axis_difference_deg, bearing_deg, distance_to_segment, project
from umi_api.pipeline.track import Track, TrackPoint

# GNSS error (~5 m in a street canyon) plus half the width of an avenue.
MAX_DISTANCE_M = 30.0
# A course further than this from a street's axis is not along that street.
MAX_HEADING_DIFF_DEG = 45.0
# How much closer another segment must be to leave the one the rider is on.
STAY_BONUS_M = 8.0
# Runs of at most this many fixes between two runs of the same segment are noise.
MAX_BLIP_FIXES = 2
# A run counts as a pass through a segment from this many fixes and metres
# (shorter ones graze a junction; routeSegments in scripts/generate-mock-data.mjs).
MIN_RUN_FIXES = 2
MIN_RUN_M = 60.0
# Grid cell side; at least MAX_DISTANCE_M so a query only looks at the 3 x 3 cells around a fix.
_CELL_M = 50.0


@dataclass(frozen=True)
class Typical:
    """What a street is usually like: physical readings and all-day scores."""

    vib_rms: float
    pm25: float
    db: float
    scores: HourScores


@dataclass(frozen=True)
class StreetRef:
    id: str
    name: str
    district_code: str
    district: str
    # [lon, lat] polyline
    coordinates: tuple[tuple[float, float], ...]
    typical: Typical


@dataclass(frozen=True)
class Candidate:
    street: StreetRef
    distance_m: float
    # Bearing of the closest edge (the street's axis there).
    axis_deg: float


@dataclass(frozen=True)
class _Edge:
    street: StreetRef
    a: XY
    b: XY
    axis_deg: float


class StreetIndex:
    """The street network in a uniform grid of edges, built once per process from the database."""

    def __init__(self, streets: Iterable[StreetRef]) -> None:
        self._streets = {s.id: s for s in streets}
        self._grid: dict[tuple[int, int], list[_Edge]] = defaultdict(list)
        for street in self._streets.values():
            points = [project(lon, lat) for lon, lat in street.coordinates]
            for a, b in itertools.pairwise(points):
                edge = _Edge(street, a, b, bearing_deg(a, b))
                (x0, y0), (x1, y1) = _cell(min(a[0], b[0]), min(a[1], b[1])), _cell(max(a[0], b[0]), max(a[1], b[1]))
                for cx in range(x0, x1 + 1):
                    for cy in range(y0, y1 + 1):
                        self._grid[cx, cy].append(edge)

    def __len__(self) -> int:
        return len(self._streets)

    def street(self, segment_id: str) -> StreetRef:
        return self._streets[segment_id]

    @cached_property
    def city_typical(self) -> Typical:
        """The mean street, for readings and scores nowhere near a known segment."""
        typical = [s.typical for s in self._streets.values()]
        return Typical(
            vib_rms=fmean(t.vib_rms for t in typical),
            pm25=fmean(t.pm25 for t in typical),
            db=fmean(t.db for t in typical),
            scores=HourScores(
                comfort=js_round(fmean(t.scores.comfort for t in typical)),
                safety=js_round(fmean(t.scores.safety for t in typical)),
                air=js_round(fmean(t.scores.air for t in typical)),
                noise=js_round(fmean(t.scores.noise for t in typical)),
            ),
        )

    def candidates(self, lon: float, lat: float, max_m: float = MAX_DISTANCE_M) -> list[Candidate]:
        """Segments within `max_m` of a point, nearest first (one candidate per segment)."""
        p = project(lon, lat)
        cx, cy = _cell(*p)
        best: dict[str, Candidate] = {}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for edge in self._grid.get((cx + dx, cy + dy), ()):
                    d = distance_to_segment(p, edge.a, edge.b)
                    if d <= max_m and (edge.street.id not in best or d < best[edge.street.id].distance_m):
                        best[edge.street.id] = Candidate(edge.street, d, edge.axis_deg)
        return sorted(best.values(), key=lambda c: c.distance_m)

    def nearest(self, lon: float, lat: float, max_m: float = MAX_DISTANCE_M) -> StreetRef | None:
        found = self.candidates(lon, lat, max_m)
        return found[0].street if found else None


def _cell(x: float, y: float) -> tuple[int, int]:
    return math.floor(x / _CELL_M), math.floor(y / _CELL_M)


@dataclass(frozen=True)
class StreetRun:
    """Consecutive track points on one segment: `first` to `last`, inclusive."""

    segment_id: str
    first: int
    last: int

    def __contains__(self, index: int) -> bool:
        return self.first <= index <= self.last


@dataclass(frozen=True)
class MatchedTrack:
    track: Track
    # Per track point; None where no segment is close enough.
    segment_ids: tuple[str | None, ...]
    # The passes: runs long enough to say something about their segment, in order.
    runs: tuple[StreetRun, ...]

    def run_at(self, index: int) -> StreetRun | None:
        return next((run for run in self.runs if index in run), None)

    @property
    def segments_matched(self) -> int:
        return len({run.segment_id for run in self.runs})


def map_match(track: Track, index: StreetIndex) -> MatchedTrack:
    segment_ids = _smooth(_match_points(track.points, index))
    return MatchedTrack(track=track, segment_ids=tuple(segment_ids), runs=tuple(_runs(segment_ids, track.points)))


def _match_points(points: Sequence[TrackPoint], index: StreetIndex) -> list[str | None]:
    matched: list[str | None] = []
    current: str | None = None
    for point in points:
        best: Candidate | None = None
        best_cost = math.inf
        for candidate in index.candidates(point.lon, point.lat):
            heading = point.heading_deg
            if heading is not None and axis_difference_deg(heading, candidate.axis_deg) > MAX_HEADING_DIFF_DEG:
                continue
            cost = candidate.distance_m - (STAY_BONUS_M if candidate.street.id == current else 0.0)
            if cost < best_cost:
                best, best_cost = candidate, cost
        if best is not None:
            current = best.street.id
        matched.append(None if best is None else best.street.id)
    return matched


def _smooth(segment_ids: list[str | None]) -> list[str | None]:
    """Relabel short blips sandwiched between two runs of the same segment."""
    spans = [(sid, len(list(group))) for sid, group in itertools.groupby(segment_ids)]
    smoothed: list[str | None] = []
    for i, (segment_id, length) in enumerate(spans):
        before = spans[i - 1][0] if i else None
        after = spans[i + 1][0] if i + 1 < len(spans) else None
        blip = length <= MAX_BLIP_FIXES and before is not None and before == after
        smoothed.extend([before if blip else segment_id] * length)
    return smoothed


def _runs(segment_ids: Sequence[str | None], points: Sequence[TrackPoint]) -> list[StreetRun]:
    runs: list[StreetRun] = []
    start = 0
    for sid, group in itertools.groupby(segment_ids):
        last = start + len(list(group)) - 1
        metres = points[last].distance_m - points[start].distance_m
        if sid is not None and last - start + 1 >= MIN_RUN_FIXES and metres >= MIN_RUN_M:
            runs.append(StreetRun(sid, start, last))
        start = last + 1
    return runs
