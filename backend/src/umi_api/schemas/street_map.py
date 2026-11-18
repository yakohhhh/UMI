"""The street map: scored segments, potholes, hard-brake hotspots, hazards and routes."""

import datetime as dt
from typing import Literal

from pydantic import Field

from umi_api.domain.enums import (
    BrakeCause,
    CityHazardStatus,
    HazardKind,
    PotholeSeverity,
    RouteGoal,
    StreetKind,
)
from umi_api.schemas.base import ApiModel, LngLat, optional
from umi_api.schemas.common import Scores


class HourlyScores(ApiModel):
    # 24 values each, 0-100, hour 0 first.
    comfort: list[int]
    safety: list[int]
    air: list[int]
    noise: list[int]


class Surface(ApiModel):
    vib_rms: float
    potholes: int


class StreetSegment(ApiModel):
    id: str
    name: str
    from_: str | None
    to: str | None
    district: str
    kind: StreetKind
    bike_lane: bool
    length_m: int
    coordinates: list[LngLat]
    scores: Scores
    hourly: HourlyScores
    passes30d: int
    # Change of the overall score vs the previous 30 days, in points.
    trend: float
    surface: Surface
    pm25: float
    db: float


class Pothole(ApiModel):
    id: str
    segment_id: str
    street: str
    coordinates: LngLat
    confirmations: int
    first_seen: dt.date
    severity: PotholeSeverity


class CauseShare(ApiModel):
    cause: BrakeCause | Literal["other"]
    share: float


class BrakeHotspot(ApiModel):
    id: str
    label: str
    coordinates: LngLat
    hard_brakes_week: int
    hard_brakes30d: int
    peak_hour: int
    trend: float
    avg_decel: float
    # Why riders brake here (shares sum to 1), only once 5+ different riders answered.
    causes: list[CauseShare] | None = optional()
    # Different riders who answered "why did you brake?" here over the period.
    answered_by: int | None = optional()


class CityHazard(ApiModel):
    """A hazard flagged by riders: never who flagged it, day-level dates only."""

    id: str
    kind: HazardKind
    street: str
    district: str
    coordinates: LngLat
    riders: int
    first_seen: dt.date
    last_confirmed: dt.date
    status: CityHazardStatus


class RouteRequest(ApiModel):
    from_: str
    to: str
    # "HH:MM" (seconds allowed, as <input type="time"> may send them), Europe/Madrid.
    depart_at: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$")
    # Street segment the rider wants to pass through.
    via: str | None = None


class PlannedRoute(ApiModel):
    id: str
    goal: RouteGoal
    label: str
    duration_min: int
    distance_m: int
    scores: Scores
    via: list[str]
    highlight: str
    coordinates: list[LngLat]
