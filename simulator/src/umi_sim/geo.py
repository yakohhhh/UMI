"""Plane geometry on a local tangent plane centred on Barcelona.

Street lengths, routing and the rider's motion are computed in metres on an
equirectangular projection around the city centre. Over the ~10 km the street
network spans, it stays within 0.1 % of the haversine distance the privacy trim
uses (same Earth radius), and interpolation along a street stays a matter of
straight lines.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence
from itertools import pairwise

from umi_protocol.constants import GEO_EARTH_RADIUS_M

type XY = tuple[float, float]
"""East, north in metres from the projection origin."""

ORIGIN_LAT = 41.39
ORIGIN_LON = 2.17

_M_PER_DEG_LAT = math.radians(1) * GEO_EARTH_RADIUS_M
_M_PER_DEG_LON = _M_PER_DEG_LAT * math.cos(math.radians(ORIGIN_LAT))


def to_xy(lon: float, lat: float) -> XY:
    return (lon - ORIGIN_LON) * _M_PER_DEG_LON, (lat - ORIGIN_LAT) * _M_PER_DEG_LAT


def to_lonlat(point: XY) -> tuple[float, float]:
    return ORIGIN_LON + point[0] / _M_PER_DEG_LON, ORIGIN_LAT + point[1] / _M_PER_DEG_LAT


def bearing_deg(a: XY, b: XY) -> float:
    """Compass bearing from ``a`` to ``b``: 0 = north, clockwise, in [0, 360)."""
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360.0


def turn_deg(from_bearing: float, to_bearing: float) -> float:
    """Signed change of direction in (-180, 180]; positive turns right."""
    delta = (to_bearing - from_bearing) % 360.0
    return delta - 360.0 if delta > 180.0 else delta


class Polyline:
    """A path in metres with its cumulative length, for interpolation and projection."""

    __slots__ = ("cumulative", "points")

    def __init__(self, points: Sequence[XY]) -> None:
        kept = [points[0]]
        for p in points[1:]:
            if math.dist(p, kept[-1]) > 1e-6:
                kept.append(p)
        if len(kept) < 2:
            raise ValueError("a polyline needs two distinct points")
        self.points: tuple[XY, ...] = tuple(kept)
        cumulative = [0.0]
        for a, b in pairwise(kept):
            cumulative.append(cumulative[-1] + math.dist(a, b))
        self.cumulative: tuple[float, ...] = tuple(cumulative)

    @property
    def length(self) -> float:
        return self.cumulative[-1]

    def _piece(self, s: float) -> int:
        """Index ``i`` of the piece ``points[i] → points[i + 1]`` that holds distance ``s``."""
        return min(max(bisect_right(self.cumulative, s) - 1, 0), len(self.points) - 2)

    def point_at(self, s: float) -> XY:
        s = min(max(s, 0.0), self.length)
        i = self._piece(s)
        a, b = self.points[i], self.points[i + 1]
        k = (s - self.cumulative[i]) / (self.cumulative[i + 1] - self.cumulative[i])
        return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k

    def bearing_at(self, s: float, smooth_m: float = 0.0) -> float:
        """Direction of travel at ``s``; ``smooth_m`` rounds corners over that distance each side."""
        if smooth_m <= 0.0:
            i = self._piece(min(max(s, 0.0), self.length))
            return bearing_deg(self.points[i], self.points[i + 1])
        lo = max(0.0, min(s - smooth_m, self.length - 2 * smooth_m))
        hi = min(self.length, max(s + smooth_m, 2 * smooth_m))
        return bearing_deg(self.point_at(lo), self.point_at(hi))

    def project(self, p: XY) -> tuple[float, float]:
        """Distance along the line of the closest point to ``p``, and how far ``p`` is from it."""
        best_s, best_d = 0.0, math.inf
        for i, (a, b) in enumerate(pairwise(self.points)):
            dx, dy = b[0] - a[0], b[1] - a[1]
            k = min(max(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy), 0.0), 1.0)
            d = math.dist(p, (a[0] + dx * k, a[1] + dy * k))
            if d < best_d:
                best_s, best_d = self.cumulative[i] + k * (self.cumulative[i + 1] - self.cumulative[i]), d
        return best_s, best_d
