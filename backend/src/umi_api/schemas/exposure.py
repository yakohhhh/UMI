import datetime as dt

from umi_api.domain.exposure import InsightTone
from umi_api.schemas.base import ApiModel


class ExposureDay(ApiModel):
    date: dt.date
    ride_min: int
    pm25: float | None
    db: float | None
    dose_ug_h: float


class ExposurePeriod(ApiModel):
    label: str
    start: str
    pm25: float | None
    db: float | None
    ride_min: int


class ExposureThresholds(ApiModel):
    who_pm25_annual: float
    who_pm25_daily: float
    eu2030_pm25: float
    who_road_noise: float


class ExposureInsight(ApiModel):
    id: str
    tone: InsightTone
    title: str
    body: str


class ExposureTotals(ApiModel):
    avg_pm25: float
    avg_db: float
    ride_hours: int
    change_pct: int
    riding_days: int
    db_change: float


class ExposureContributor(ApiModel):
    street: str
    share: float
    pm25: float
    minutes_week: int


class ExposureSummary(ApiModel):
    days: list[ExposureDay]
    weekly: list[ExposurePeriod]
    monthly: list[ExposurePeriod]
    thresholds: ExposureThresholds
    insights: list[ExposureInsight]
    totals: ExposureTotals
    # Streets that contribute most to the rider's PM2.5 dose (last 90 days).
    contributors: list[ExposureContributor]
