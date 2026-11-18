"""Vocabularies shared by the API, the database and the pipeline (src/lib/types.ts).

Values are the strings the web app uses. Where the Clip has a wire code for the
same idea (activity, event kind, flag source, hazard kind), the names match
`umi_protocol.constants` and a test keeps them in step.
"""

from enum import StrEnum


class ActivityType(StrEnum):
    RIDE = "ride"
    RUN = "run"


class RideEventType(StrEnum):
    HARD_BRAKE = "hard_brake"
    POTHOLE = "pothole"
    # Derived on the server from AIR and SAMPLE records, not detected on the Clip.
    PM_SPIKE = "pm_spike"
    NOISE_PEAK = "noise_peak"


class BrakeCause(StrEnum):
    PEDESTRIAN = "pedestrian"
    ANIMAL = "animal"
    VEHICLE = "vehicle"
    CAR_DOOR = "car_door"
    LANE_BLOCKED = "lane_blocked"
    SURFACE = "surface"
    ROADWORKS = "roadworks"
    JUNCTION = "junction"
    JUST_ME = "just_me"


class CauseBucket(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    BEHAVIOUR = "behaviour"
    PERSONAL = "personal"


class HazardKind(StrEnum):
    ROADWORKS = "roadworks"
    POTHOLE = "pothole"
    BLOCKED_LANE = "blocked_lane"
    OBSTACLE = "obstacle"
    DANGER = "danger"


class FlagSource(StrEnum):
    PRESS = "press"
    VOICE = "voice"


class HazardStatus(StrEnum):
    """Lifecycle of a flagged hazard, shown on each rider's flags (FlagStatus in the web)."""

    PENDING = "pending"
    VERIFIED = "verified"
    SENT_TO_CITY = "sent_to_city"
    FIXED = "fixed"
    EXPIRED = "expired"


class ConfirmationSource(StrEnum):
    """How a rider confirmed a hazard."""

    # Pressed the button there.
    FLAG = "flag"
    # Their Clip passed with the same sensor signature (swerve, impact).
    SENSOR = "sensor"


class CityHazardStatus(StrEnum):
    """Where the city's own process is with a published hazard (IRIS)."""

    NEW = "new"
    SENT_TO_IRIS = "sent_to_iris"
    SCHEDULED = "scheduled"
    FIXED = "fixed"


class ScoreDimension(StrEnum):
    COMFORT = "comfort"
    SAFETY = "safety"
    AIR = "air"
    NOISE = "noise"


class StreetKind(StrEnum):
    ARTERIAL = "arterial"
    BOULEVARD = "boulevard"
    STREET = "street"
    GREEN = "green"
    PROMENADE = "promenade"
    SEAFRONT = "seafront"


class PotholeSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RouteGoal(StrEnum):
    FASTEST = "fastest"
    CALMEST = "calmest"
    CLEANEST = "cleanest"


class KpiDirection(StrEnum):
    UP = "up"
    DOWN = "down"


class Period(StrEnum):
    WEEK = "7d"
    MONTH = "30d"
    QUARTER = "90d"
    YEAR = "12m"


class Mode(StrEnum):
    ALL = "all"
    BIKE = "bike"
    RUN = "run"
