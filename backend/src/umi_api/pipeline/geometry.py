"""Planar geometry in metres, for map matching and trace simplification.

Barcelona spans about 15 km: projected equirectangularly around the city centre,
distances between nearby points are off by less than 0.2 %, far below GNSS error,
so street matching can work in a flat plane.
"""

import math
from collections.abc import Iterable, Sequence

from umi_protocol.constants import GEO_EARTH_RADIUS_M

from umi_api.domain.geo import BBox

XY = tuple[float, float]

_ORIGIN_LON, _ORIGIN_LAT = 2.17, 41.39
_M_PER_DEG_LAT = math.radians(1) * GEO_EARTH_RADIUS_M
_M_PER_DEG_LON = _M_PER_DEG_LAT * math.cos(math.radians(_ORIGIN_LAT))


def project(lon: float, lat: float) -> XY:
    """Metres east and north of the city centre."""
    return (lon - _ORIGIN_LON) * _M_PER_DEG_LON, (lat - _ORIGIN_LAT) * _M_PER_DEG_LAT


def bbox_around(points: Iterable[tuple[float, float]], margin_m: float) -> BBox:
    """Bounding box (min_lon, min_lat, max_lon, max_lat) of [lon, lat] points, grown by `margin_m` on every side."""
    lons, lats = zip(*points, strict=True)
    d_lon, d_lat = margin_m / _M_PER_DEG_LON, margin_m / _M_PER_DEG_LAT
    return min(lons) - d_lon, min(lats) - d_lat, max(lons) + d_lon, max(lats) + d_lat


def bearing_deg(a: XY, b: XY) -> float:
    """Direction from `a` to `b`, clockwise from north, in [0, 360)."""
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360


def axis_difference_deg(heading_deg: float, axis_deg: float) -> float:
    """Angle between a direction of travel and a street axis, which can be ridden both ways: [0, 90]."""
    diff = abs(heading_deg - axis_deg) % 180
    return min(diff, 180 - diff)


def distance_to_segment(p: XY, a: XY, b: XY) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def simplify(points: Sequence[XY], tolerance_m: float) -> list[int]:
    """Douglas-Peucker: indices of the points to keep, first and last included, in order."""
    if len(points) < 3:
        return list(range(len(points)))
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        far, far_d = -1, tolerance_m
        for i in range(first + 1, last):
            d = distance_to_segment(points[i], points[first], points[last])
            if d > far_d:
                far, far_d = i, d
        if far >= 0:
            keep[far] = True
            stack.extend(((first, far), (far, last)))
    return [i for i, kept in enumerate(keep) if kept]
