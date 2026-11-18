"""Great-circle distance, computed the same way by every component.

The privacy trim must cut at the same sample on the phone, in the simulator and in
the backend's checks, so the formula and the radius are part of the protocol:
``d = 2·R·asin(√a)`` with ``a = sin²(Δφ/2) + cos φ₁·cos φ₂·sin²(Δλ/2)`` and
``R = [geo] earth_radius_m``.
"""

from __future__ import annotations

import math

from .constants import GEO_EARTH_RADIUS_M


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in metres between two points given in degrees."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    a = (
        math.sin((phi2 - phi1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    # min() guards against a rounding a hair above 1 for antipodal points.
    return 2 * GEO_EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))
