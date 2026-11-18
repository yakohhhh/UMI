"""What an uploaded session must look like to be believed.

Telemetry is not signed (the phone trims it), so its integrity rests on the
paired Clip, the authenticated rider and these checks (protocol/README.md §1.4).
A check either drops the records it cannot believe, or refuses the whole
session when too little would be left to make sense of it.
"""

from datetime import timedelta

from umi_api.domain.enums import ActivityType
from umi_api.domain.geo import BBox

# Barcelona's municipal boundary (min_lon, min_lat, max_lon, max_lat), rounded out to 0.01°.
# Positions outside it cannot be scored against the street network.
SERVICE_AREA: BBox = (2.05, 41.31, 2.23, 41.47)

# GNSS speeds above these are glitches (or the Clip is in a car or on a train).
MAX_SPEED_KMH: dict[ActivityType, float] = {ActivityType.RIDE: 60.0, ActivityType.RUN: 30.0}
# Above this share of implausibly fast fixes, the session is not the activity it claims to be.
MAX_TOO_FAST_SHARE = 0.2
# A Clip that did not say what it records: faster than this (median while moving) is a ride.
RIDE_FROM_MEDIAN_KMH = 12.0

# The session must have ended by "now" give or take this much clock drift...
CLOCK_TOLERANCE = timedelta(minutes=5)
# ...and not be older than this: the Clip keeps sessions until the phone confirms an upload,
# but a year-old ride says nothing about the streets today.
MAX_SESSION_AGE = timedelta(days=366)

# Flags kept per rider and Barcelona day; beyond this, flags are dropped (counted as rejected).
# Nobody meets that many distinct hazards in a day: it caps what one Clip can push to the map.
MAX_FLAGS_PER_RIDER_DAY = 20


def in_service_area(lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = SERVICE_AREA
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat
