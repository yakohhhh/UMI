"""City Insights filters (period, districts, Bike / Run / All) applied to the city aggregates.

The stored aggregates are one snapshot: weekly rides per district, 30-day
hotspot counts, a 12-month brake series and an hour x weekday air and noise
matrix. Until the pipeline aggregates segment passes per period and mode, the
filters rescale that snapshot with the factors below, ported from
src/lib/api.ts so the dashboard reads the same as on the mocks. Rider counts
that decide what is published (hazards, cause mixes) are never rescaled: they
are counted from distinct riders for the period.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from umi_api.domain.enums import KpiDirection, Mode, Period
from umi_api.domain.numbers import js_round, round_to

PERIOD_FACTOR: dict[Period, float] = {Period.WEEK: 1, Period.MONTH: 4.3, Period.QUARTER: 12.9, Period.YEAR: 52}
MODE_FACTOR: dict[Mode, float] = {Mode.ALL: 1, Mode.BIKE: 0.82, Mode.RUN: 0.18}
# Runners brake hard far less than riders.
MODE_BRAKES: dict[Mode, float] = {Mode.ALL: 1, Mode.BIKE: 0.97, Mode.RUN: 0.05}
MONTHS_IN: dict[Period, float] = {Period.WEEK: 1 / 4.3, Period.MONTH: 1, Period.QUARTER: 3, Period.YEAR: 12}

# A junction is an "active" hotspot from this many hard brakes a week.
ACTIVE_HOTSPOT_PER_WEEK = 8
# The monthly series stores a sampled count; the city-wide total is ~4.2x (all riders, not only the panel).
MONTHLY_BRAKE_SCALE = 4.2
# Mean PM2.5 on the streets runners use, away from the arterials.
RUN_PM25_KPI = 11.6


@dataclass(frozen=True)
class CityFilters:
    period: Period = Period.MONTH
    mode: Mode = Mode.ALL
    districts: tuple[str, ...] = ()

    def includes(self, district: str | None) -> bool:
        return not self.districts or district in self.districts


@dataclass(frozen=True)
class Kpi:
    id: str
    label: str
    value: float
    unit: str
    delta: float
    delta_unit: str
    better: KpiDirection
    spark: list[float]
    delta_label: str | None = None
    limit: float | None = None
    limit_label: str | None = None


@dataclass(frozen=True)
class DistrictFigures:
    name: str
    code: str
    comfort: int
    safety: int
    air: int
    noise: int
    surface_index: float
    rides_week: int
    km_measured: float
    hotspots: int
    pm25: float
    db: float


@dataclass(frozen=True)
class MonthlyBrakes:
    month: str
    hard_brakes: int
    rides: int


@dataclass(frozen=True)
class SafetyTotals:
    hard_brakes: int
    per_thousand_rides: float
    delta: float
    active_hotspots: int
    at_hotspots_pct: int


@dataclass(frozen=True)
class AirNoiseCell:
    pm25: float
    db: float
    rides: int


class MonthlyBrakesLike(Protocol):
    @property
    def month(self) -> str: ...
    @property
    def hard_brakes(self) -> int: ...
    @property
    def rides(self) -> int: ...


class AirNoiseLike(Protocol):
    @property
    def pm25(self) -> float: ...
    @property
    def db(self) -> float: ...
    @property
    def rides(self) -> int: ...


class HotspotCounts(Protocol):
    @property
    def hard_brakes_week(self) -> int: ...
    @property
    def hard_brakes30d(self) -> int: ...


def scale_rides(rides_week: float, f: CityFilters) -> int:
    return js_round(rides_week * PERIOD_FACTOR[f.period] * MODE_FACTOR[f.mode])


def scale_kpi(kpi: Kpi, f: CityFilters) -> Kpi:
    if kpi.id == "rides":
        unit = "this week" if f.period is Period.WEEK else f"last {f.period}"
        return replace(kpi, value=scale_rides(kpi.value, f), unit=unit, spark=[scale_rides(x, f) for x in kpi.spark])
    if kpi.id == "pm25" and f.mode is Mode.RUN:
        return replace(kpi, value=RUN_PM25_KPI, spark=[round_to(x * 0.82, 1) for x in kpi.spark])
    return kpi


def district_kpis(kpis: Sequence[Kpi], districts: Sequence[DistrictFigures], f: CityFilters) -> list[Kpi]:
    """Headline figures re-aggregated over the selected districts (km-weighted)."""
    selected = [d for d in districts if f.includes(d.name)]
    if not f.districts or not selected:
        return list(kpis)
    km = sum(d.km_measured for d in selected)
    all_km = sum(d.km_measured for d in districts) or 1

    def weighted(values: Sequence[float]) -> float:
        return sum(v * d.km_measured for v, d in zip(values, selected, strict=True)) / (km or 1)

    figures: dict[str, float] = {
        "km": round_to(km, 1),
        "rides": sum(d.rides_week for d in selected),
        "surface": round_to(weighted([d.surface_index for d in selected]), 1),
        "hotspots": sum(d.hotspots for d in selected),
        "pm25": round_to(weighted([d.pm25 for d in selected]), 1),
    }
    out = []
    for kpi in kpis:
        if kpi.id not in figures:
            out.append(kpi)
            continue
        value = figures[kpi.id]
        ratio = value / kpi.value if kpi.value else km / all_km
        out.append(replace(kpi, value=value, spark=[round_to(x * ratio, 1) for x in kpi.spark]))
    return out


def scale_surface(confirmed_impacts: int, riders30d: int, f: CityFilters) -> tuple[int, int]:
    """Confirmed impacts grow sub-linearly with the period (the same potholes keep being felt)."""
    impacts = js_round(confirmed_impacts * min(3, math.sqrt(PERIOD_FACTOR[f.period] / 4.3)))
    return impacts, js_round(riders30d * MODE_FACTOR[f.mode])


def scale_hotspot(hard_brakes30d: int, hard_brakes_week: int, f: CityFilters) -> tuple[int, int]:
    """(brakes over the period, brakes this week) for the selected mode."""
    mode_brakes = MODE_BRAKES[f.mode]
    factor = (PERIOD_FACTOR[f.period] / 4.3) * mode_brakes
    floor = 0 if f.mode is Mode.RUN else 1
    return max(1, js_round(hard_brakes30d * factor)), max(floor, js_round(hard_brakes_week * mode_brakes))


def monthly_brakes(series: Sequence[MonthlyBrakesLike], f: CityFilters, district_share: float) -> list[MonthlyBrakes]:
    """`district_share` = share of the hotspots in the selected districts (1 without a district filter)."""
    rides_share = max(0.08, district_share) if f.districts else 1
    return [
        MonthlyBrakes(
            month=m.month,
            hard_brakes=js_round(m.hard_brakes * MONTHLY_BRAKE_SCALE * MODE_BRAKES[f.mode] * district_share),
            rides=js_round(m.rides * MODE_FACTOR[f.mode] * rides_share),
        )
        for m in series
    ]


def safety_totals(monthly: Sequence[MonthlyBrakes], hotspots: Sequence[HotspotCounts], f: CityFilters) -> SafetyTotals:
    """Totals over the selected period, compared with the same window just before it."""
    months = MONTHS_IN[f.period]
    whole = max(1, math.ceil(months))

    def window(end: int) -> tuple[float, float]:
        part = monthly[max(0, end - whole) : max(0, end)]
        k = months / whole
        return sum(m.hard_brakes for m in part) * k, sum(m.rides for m in part) * k

    def rate(brakes: float, rides: float) -> float:
        return brakes / rides * 1000 if rides else 0

    now_brakes, now_rides = window(len(monthly))
    prev_brakes, prev_rides = window(len(monthly) - whole)
    now_rate, prev_rate = rate(now_brakes, now_rides), rate(prev_brakes, prev_rides)
    at_hotspots = sum(h.hard_brakes30d for h in hotspots)
    total = max(js_round(now_brakes), at_hotspots)
    return SafetyTotals(
        hard_brakes=total,
        per_thousand_rides=round_to(now_rate, 1),
        delta=js_round((now_rate - prev_rate) / prev_rate * 1000) / 10 if prev_rides and prev_rate else 0,
        active_hotspots=sum(1 for h in hotspots if h.hard_brakes_week >= ACTIVE_HOTSPOT_PER_WEEK),
        at_hotspots_pct=js_round(at_hotspots / total * 100) if total else 0,
    )


def scale_air_noise(matrix: Sequence[Sequence[AirNoiseLike]], f: CityFilters) -> list[list[AirNoiseCell]]:
    seasonal = 1.04 if f.period is Period.YEAR else 0.97 if f.period is Period.QUARTER else 1
    district = (1 + (0.08 if "Eixample" in f.districts else -0.04)) if f.districts else 1
    louder = 1.2 if district > 1 else 0
    return [
        [
            AirNoiseCell(
                pm25=round_to(cell.pm25 * seasonal * district, 1),
                db=round_to(cell.db + louder, 1),
                rides=js_round(cell.rides * MODE_FACTOR[f.mode] * PERIOD_FACTOR[f.period]),
            )
            for cell in row
        ]
        for row in matrix
    ]
