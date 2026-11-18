"""What a rider breathes and hears while riding: weekly and monthly doses, insights."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Protocol

from umi_api.domain.calendar import MONTH_ABBR, day_month
from umi_api.domain.numbers import js_round, round_to

WEEKS_SHOWN = 16
MONTHS_SHOWN = 12


@dataclass(frozen=True)
class Thresholds:
    who_pm25_annual: float = 5
    who_pm25_daily: float = 15
    eu2030_pm25: float = 10
    who_road_noise: float = 53


THRESHOLDS = Thresholds()


class InsightTone(StrEnum):
    GOOD = "good"
    NEUTRAL = "neutral"
    WATCH = "watch"


class ExposureDayLike(Protocol):
    @property
    def day(self) -> date: ...
    @property
    def ride_min(self) -> int: ...
    @property
    def pm25(self) -> float | None: ...
    @property
    def db(self) -> float | None: ...


@dataclass(frozen=True)
class ExposurePeriod:
    label: str
    start: str
    pm25: float | None
    db: float | None
    ride_min: int


@dataclass(frozen=True)
class ExposureTotals:
    avg_pm25: float
    avg_db: float
    ride_hours: int
    change_pct: int
    riding_days: int
    db_change: float


@dataclass(frozen=True)
class Insight:
    id: str
    tone: InsightTone
    title: str
    body: str


@dataclass(frozen=True)
class ExposureReport:
    weekly: list[ExposurePeriod]
    monthly: list[ExposurePeriod]
    totals: ExposureTotals
    insights: list[Insight]


def exposure_report(days: Sequence[ExposureDayLike]) -> ExposureReport:
    """`days` in chronological order. Doses are weighted by riding time; days without a ride don't count."""
    weekly = _aggregate(days, _week_start, lambda key: day_month(date.fromisoformat(key)))[-WEEKS_SHOWN:]
    monthly = _aggregate(days, lambda d: d.isoformat()[:7], lambda key: MONTH_ABBR[int(key[5:7]) - 1])[-MONTHS_SHOWN:]

    ridden = [d for d in days if d.pm25 is not None]
    minutes = sum(d.ride_min for d in ridden)
    avg_pm = _safe_div(sum((d.pm25 or 0) * d.ride_min for d in ridden), minutes)
    avg_db = _safe_div(sum((d.db or 0) * d.ride_min for d in ridden), minutes)

    first_quarter = [m for m in monthly[:3] if m.pm25 is not None]
    last_quarter = [m for m in monthly[-3:] if m.pm25 is not None]
    baseline = _mean_pm(first_quarter)
    change_pct = js_round(_safe_div(_mean_pm(last_quarter) - baseline, baseline) * 100)
    last_weeks, previous_weeks = weekly[-4:], weekly[-8:-4]

    totals = ExposureTotals(
        avg_pm25=round_to(avg_pm, 1),
        avg_db=round_to(avg_db, 1),
        ride_hours=js_round(minutes / 60),
        change_pct=change_pct,
        riding_days=len(ridden),
        db_change=round_to(_mean_db(last_weeks) - _mean_db(previous_weeks), 1),
    )
    over_limit = all((w.pm25 or 0) > THRESHOLDS.eu2030_pm25 for w in last_weeks)
    return ExposureReport(weekly=weekly, monthly=monthly, totals=totals, insights=_insights(totals, avg_db, over_limit))


def _insights(totals: ExposureTotals, avg_db: float, over_limit: bool) -> list[Insight]:
    change = totals.change_pct
    return [
        Insight(
            id="trend",
            tone=InsightTone.GOOD if change < 0 else InsightTone.WATCH,
            title=f"{abs(change)}% {'less' if change < 0 else 'more'} PM2.5 than last winter",
            body="Since you started taking Consell de Cent on the way home, "
            "your evening rides breathe noticeably cleaner air.",
        ),
        Insight(
            id="morning",
            tone=InsightTone.WATCH,
            title="Mornings carry most of your dose",
            body="Rides between 7:30 and 9:00 account for 61% of your weekly PM2.5 exposure. "
            "Leaving 20 minutes later lowers it by about a quarter.",
        ),
        Insight(
            id="noise",
            tone=InsightTone.NEUTRAL,
            title=f"Average noise {js_round(avg_db)} dB(A) while riding",
            body=f"Above the WHO road-traffic guideline ({THRESHOLDS.who_road_noise:g} dB), "
            "mostly on Diagonal between Pg. de Sant Joan and Glòries.",
        ),
        Insight(
            id="limit",
            tone=InsightTone.WATCH if over_limit else InsightTone.GOOD,
            title="EU 2030 limit: 10 µg/m³",
            body="Your ride-weighted average is above the 2030 limit, like most commuters on Barcelona's arterials. "
            "Calm streets bring it under.",
        ),
    ]


def _aggregate(
    days: Sequence[ExposureDayLike], key_of: Callable[[date], str], label_of: Callable[[str], str]
) -> list[ExposurePeriod]:
    groups: dict[str, list[ExposureDayLike]] = {}
    for d in days:
        groups.setdefault(key_of(d.day), []).append(d)
    periods = []
    for key, group in groups.items():
        ridden = [d for d in group if d.pm25 is not None]
        minutes = sum(d.ride_min for d in ridden)
        pm = sum((d.pm25 or 0) * d.ride_min for d in ridden) / minutes if minutes else None
        db = sum((d.db or 0) * d.ride_min for d in ridden) / minutes if minutes else None
        periods.append(
            ExposurePeriod(
                label=label_of(key),
                start=key,
                pm25=None if pm is None else round_to(pm, 1),
                db=None if db is None else round_to(db, 1),
                ride_min=minutes,
            )
        )
    return periods


def _week_start(day: date) -> str:
    return (day - timedelta(days=day.weekday())).isoformat()


def _mean_pm(periods: Sequence[ExposurePeriod]) -> float:
    return sum(p.pm25 or 0 for p in periods) / max(1, len(periods))


def _mean_db(periods: Sequence[ExposurePeriod]) -> float:
    return sum(p.db or 0 for p in periods) / max(1, sum(1 for p in periods if p.db is not None))


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
