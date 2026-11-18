from typing import Any

from pydantic import SerializerFunctionWrapHandler, model_serializer

from umi_api.domain.enums import ActivityType, BrakeCause, FlagSource, HazardKind, HazardStatus, RideEventType
from umi_api.schemas.base import ApiModel, IsoDateTime, LngLat, optional
from umi_api.schemas.common import Scores

# [t (s), distance (m), speed (km/h), vibration (m/s² RMS), PM2.5 (µg/m³), noise (dB), route index]
ActivitySample = tuple[float, float, float, float, float, float, int]


class RideEvent(ApiModel):
    # "{activityId}-e{index}"
    id: str
    type: RideEventType
    sample_index: int
    coordinates: LngLat
    # m/s² for brakes (mean deceleration) and potholes (1 s vibration RMS), as the Clip's EVENT
    # record says (protocol/README.md §1.3); µg/m³ for PM2.5, dB(A) for noise.
    value: float
    # HH:mm, Europe/Madrid
    time: str
    street: str | None
    # Hard brakes only: the rider's answer (null while unanswered) and whether the app asks about it.
    cause: BrakeCause | None = None
    ask: bool = False

    @model_serializer(mode="wrap")
    def _brake_fields_on_brakes_only(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if self.type is not RideEventType.HARD_BRAKE:
            data.pop("cause", None)
            data.pop("ask", None)
        return data


class RideFlag(ApiModel):
    id: str
    sample_index: int
    coordinates: LngLat
    time: str
    street: str | None
    # None = pressed without a keyword; the rider says what it was after the ride.
    kind: HazardKind | None
    source: FlagSource
    status: HazardStatus
    # Other riders whose Clips confirmed it, with a press or the same sensor signature.
    confirmations: int
    riders_warned: int
    proof: str | None = optional()


class Weather(ApiModel):
    temp_c: float
    condition: str


class ActivitySummary(ApiModel):
    id: str
    athlete_id: str
    type: ActivityType
    title: str
    place: str
    description: str | None
    started_at: IsoDateTime
    duration_s: int
    moving_time_s: int
    distance_m: int
    avg_speed_kmh: float
    max_speed_kmh: float
    elevation_gain_m: int
    scores: Scores
    events: list[RideEvent]
    flags: list[RideFlag]
    preview: list[LngLat]
    kudos: int
    kudoed_by: list[str]
    comments: int
    featured: bool
    weather: Weather


class ActivitySegment(ApiModel):
    segment_id: str
    name: str
    from_: str | None
    to: str | None
    distance_m: int
    score: int
    street_average: int
    bike_lane: bool


class ActivityDetail(ActivitySummary):
    route: list[LngLat]
    samples: list[ActivitySample]
    segments: list[ActivitySegment]


class FlagReport(RideFlag):
    activity_id: str
    # YYYY-MM-DD, Barcelona
    date: str


class CauseAnswer(ApiModel):
    cause: BrakeCause


class KindAnswer(ApiModel):
    kind: HazardKind
