"""City Insights: overview, surface, safety, air and noise."""

from umi_api.domain.city_alerts import AlertTone
from umi_api.domain.enums import KpiDirection
from umi_api.schemas.base import ApiModel, IsoDateTime, optional
from umi_api.schemas.common import Scores
from umi_api.schemas.street_map import BrakeHotspot


class Kpi(ApiModel):
    id: str
    label: str
    value: float
    unit: str
    delta: float
    delta_unit: str
    # What the delta compares against, e.g. "vs last winter" (default "vs prev.").
    delta_label: str | None = optional()
    better: KpiDirection
    spark: list[float]
    limit: float | None = optional()
    limit_label: str | None = optional()


class DistrictStat(ApiModel):
    name: str
    code: str
    scores: Scores
    surface_index: float
    rides_week: int
    km_measured: float
    hotspots: int
    pm25: float
    db: float


class CityAlert(ApiModel):
    id: str
    tone: AlertTone
    title: str
    body: str
    href: str


class CityOverview(ApiModel):
    kpis: list[Kpi]
    # Every district (maps need the whole city); the UI highlights the selection.
    districts: list[DistrictStat]
    alerts: list[CityAlert]
    generated_at: IsoDateTime


class SurfaceRankRow(ApiModel):
    segment_id: str
    street: str
    from_: str | None
    to: str | None
    district: str
    surface_index: float
    confirmed_impacts: int
    riders30d: int
    trend: float
    length_m: int


class MonthlyBrakes(ApiModel):
    month: str
    hard_brakes: int
    rides: int


class SafetyTotals(ApiModel):
    hard_brakes: int
    per_thousand_rides: float
    # Change of the per-1,000-rides rate vs the previous period, in %.
    delta: float
    # Clusters with at least 8 hard brakes a week.
    active_hotspots: int
    # Share of all hard brakes that happen at a hotspot.
    at_hotspots_pct: int


class SafetyData(ApiModel):
    hotspots: list[BrakeHotspot]
    monthly: list[MonthlyBrakes]
    totals: SafetyTotals


class AirNoiseCell(ApiModel):
    pm25: float
    db: float
    rides: int
