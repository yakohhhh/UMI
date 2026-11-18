"""The web app's mock datasets (src/lib/mock/data/*.json), read as typed records.

Shapes follow src/lib/types.ts; only the fields the seed reads are declared.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

LngLat = list[float]


class AthleteJson(TypedDict):
    id: str
    name: str
    firstName: str
    initials: str
    age: int
    city: str
    vehicle: str


class PeopleJson(TypedDict):
    people: dict[str, AthleteJson]


class ScoresJson(TypedDict):
    comfort: int
    safety: int
    air: int
    noise: int


class EventJson(TypedDict):
    type: str
    sampleIndex: int
    coordinates: LngLat
    value: float
    time: str
    street: str | None


class WeatherJson(TypedDict):
    tempC: float
    condition: str


class ActivityJson(TypedDict):
    id: str
    athleteId: str
    type: str
    title: str
    place: str
    description: str | None
    startedAt: str
    durationS: int
    movingTimeS: int
    distanceM: int
    avgSpeedKmh: float
    maxSpeedKmh: float
    elevationGainM: int
    scores: ScoresJson
    events: list[EventJson]
    preview: list[LngLat]
    kudos: int
    kudoedBy: list[str]
    comments: int
    featured: bool
    weather: WeatherJson


class ActivitySegmentJson(TypedDict):
    segmentId: str
    distanceM: int
    score: int
    streetAverage: int


class ActivityDetailJson(TypedDict):
    route: list[LngLat]
    samples: list[list[float]]
    segments: list[ActivitySegmentJson]


class HourlyJson(TypedDict):
    comfort: list[int]
    safety: list[int]
    air: list[int]
    noise: list[int]


class SurfaceJson(TypedDict):
    vibRms: float


# Functional form: "from" is a Python keyword.
StreetJson = TypedDict(
    "StreetJson",
    {
        "id": str,
        "name": str,
        "from": str | None,
        "to": str | None,
        "district": str,
        "kind": str,
        "bikeLane": bool,
        "lengthM": int,
        "coordinates": list[LngLat],
        "scores": ScoresJson,
        "hourly": HourlyJson,
        "passes30d": int,
        "trend": float,
        "surface": SurfaceJson,
        "pm25": float,
        "db": float,
    },
)


class PotholeJson(TypedDict):
    id: str
    segmentId: str
    coordinates: LngLat
    confirmations: int
    firstSeen: str
    severity: str


class HotspotJson(TypedDict):
    id: str
    label: str
    coordinates: LngLat
    hardBrakesWeek: int
    hardBrakes30d: int
    peakHour: int
    trend: float
    avgDecel: float


class FeatureJson(TypedDict):
    properties: dict[str, str]
    geometry: dict[str, object]


class FeatureCollectionJson(TypedDict):
    features: list[FeatureJson]


class KpiJson(TypedDict):
    id: str
    label: str
    value: float
    unit: str
    delta: float
    deltaUnit: str
    deltaLabel: NotRequired[str]
    better: str
    spark: list[float]
    limit: NotRequired[float]
    limitLabel: NotRequired[str]


class DistrictStatJson(TypedDict):
    name: str
    code: str
    scores: ScoresJson
    surfaceIndex: float
    ridesWeek: int
    kmMeasured: float
    pm25: float
    db: float


class MonthlyBrakesJson(TypedDict):
    month: str
    hardBrakes: int
    rides: int


class AirNoiseJson(TypedDict):
    pm25: float
    db: float
    rides: int


class CityJson(TypedDict):
    generatedAt: str
    kpis: list[KpiJson]
    districts: list[DistrictStatJson]
    monthlyHardBrakes: list[MonthlyBrakesJson]
    airNoise: list[list[AirNoiseJson]]


class ExposureDayJson(TypedDict):
    date: str
    rideMin: int
    pm25: float | None
    db: float | None
    doseUgH: float


class RouteJson(TypedDict):
    id: str
    goal: str
    label: str
    durationMin: int
    distanceM: int
    scores: ScoresJson
    via: list[str]
    highlight: str
    coordinates: list[LngLat]


class SurfaceRankJson(TypedDict):
    segmentId: str
    surfaceIndex: float
    confirmedImpacts: int
    riders30d: int
    trend: float


class FlagJson(TypedDict):
    id: str
    sampleIndex: int
    coordinates: LngLat
    time: str
    street: str | None
    kind: str | None
    source: str
    status: str
    confirmations: int
    ridersWarned: int
    proof: NotRequired[str]


class BrakeAnswerJson(TypedDict):
    cause: str | None
    ask: NotRequired[bool]


class CityHazardJson(TypedDict):
    id: str
    kind: str
    street: str
    district: str
    coordinates: LngLat
    riders: int
    firstSeen: str
    lastConfirmed: str
    status: str


class FlagsJson(TypedDict):
    flags: dict[str, list[FlagJson]]
    # Flag id -> the city hazard it joined.
    flagHazards: dict[str, str]
    brakeAnswers: dict[str, BrakeAnswerJson]
    cityHazards: list[CityHazardJson]


@dataclass(frozen=True)
class MockData:
    people: PeopleJson
    activities: list[ActivityJson]
    details: dict[str, ActivityDetailJson]
    streets: list[StreetJson]
    potholes: list[PotholeJson]
    hotspots: list[HotspotJson]
    districts: FeatureCollectionJson
    city_outline: FeatureCollectionJson
    city: CityJson
    exposure: list[ExposureDayJson]
    routes: list[RouteJson]
    surface_ranking: list[SurfaceRankJson]
    flags: FlagsJson


def load_mock_data(data_dir: Path) -> MockData:
    def read(name: str) -> Any:
        path = data_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"mock dataset not found: {path} (set UMI_MOCK_DATA_DIR)")
        return json.loads(path.read_text(encoding="utf-8"))

    return MockData(
        people=cast(PeopleJson, read("people.json")),
        activities=cast(list[ActivityJson], read("activities.json")),
        details=cast(dict[str, ActivityDetailJson], read("activity-details.json")),
        streets=cast(list[StreetJson], read("streets.json")),
        potholes=cast(list[PotholeJson], read("potholes.json")),
        hotspots=cast(list[HotspotJson], read("hotspots.json")),
        districts=cast(FeatureCollectionJson, read("districts.json")),
        city_outline=cast(FeatureCollectionJson, read("city-outline.json")),
        city=cast(CityJson, read("city.json")),
        exposure=cast(list[ExposureDayJson], read("exposure.json")),
        routes=cast(list[RouteJson], read("routes.json")),
        surface_ranking=cast(list[SurfaceRankJson], read("surface-ranking.json")),
        flags=cast(FlagsJson, read("flags.json")),
    )
