"""Small geometry helpers on WGS84 coordinates ([lon, lat], like GeoJSON)."""

from collections.abc import Iterable, Sequence
from typing import Protocol

# At Barcelona's latitude a degree of latitude is ~1.33x longer than a degree of longitude.
LAT_STRETCH = 1.33

LngLat = tuple[float, float]


class PlacedSegment(Protocol):
    @property
    def district(self) -> str: ...
    @property
    def coordinates(self) -> Sequence[Sequence[float]]: ...


def nearest_segment_district(point: LngLat, segments: Iterable[PlacedSegment]) -> str | None:
    """District of the street segment with the closest vertex to `point`."""
    best, district = float("inf"), None
    for segment in segments:
        for x, y in segment.coordinates:
            d = (x - point[0]) ** 2 + ((y - point[1]) * LAT_STRETCH) ** 2
            if d < best:
                best, district = d, segment.district
    return district


BBox = tuple[float, float, float, float]


def overlaps_bbox(coordinates: Sequence[Sequence[float]], bbox: BBox) -> bool:
    """Whether a line's bounding box overlaps `bbox` (min_lon, min_lat, max_lon, max_lat).

    Conservative on purpose: a map may draw a segment that only grazes the view.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    xs = [p[0] for p in coordinates]
    ys = [p[1] for p in coordinates]
    return min(xs) <= max_lon and max(xs) >= min_lon and min(ys) <= max_lat and max(ys) >= min_lat
