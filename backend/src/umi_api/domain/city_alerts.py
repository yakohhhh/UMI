"""What changed: the few signals a mobility team should look at first."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol

from umi_api.domain.calendar import WEEKDAY_NAMES, day_month
from umi_api.domain.enums import CityHazardStatus, HazardKind
from umi_api.domain.exposure import THRESHOLDS
from umi_api.domain.numbers import js_number, js_round

# A junction "eases" only if it was busy to begin with.
EASING_MIN_PER_WEEK = 15
# Below this surface index a street needs resurfacing.
ROUGH_BELOW = 35

HAZARD_NOUN: dict[HazardKind, str] = {
    HazardKind.ROADWORKS: "roadworks",
    HazardKind.POTHOLE: "a pothole",
    HazardKind.BLOCKED_LANE: "a blocked bike lane",
    HazardKind.OBSTACLE: "an obstacle",
    HazardKind.DANGER: "a dangerous spot",
}


class AlertTone(StrEnum):
    GOOD = "good"
    MID = "mid"
    BAD = "bad"


@dataclass(frozen=True)
class CityAlert:
    id: str
    tone: AlertTone
    title: str
    body: str
    href: str


class AlertHotspot(Protocol):
    @property
    def label(self) -> str: ...
    @property
    def trend(self) -> float: ...
    @property
    def hard_brakes_week(self) -> int: ...
    @property
    def peak_hour(self) -> int: ...


class AlertSegment(Protocol):
    @property
    def street(self) -> str: ...
    @property
    def from_(self) -> str | None: ...
    @property
    def to(self) -> str | None: ...
    @property
    def surface_index(self) -> float: ...
    @property
    def riders30d(self) -> int: ...
    @property
    def confirmed_impacts(self) -> int: ...


class AlertHazard(Protocol):
    @property
    def kind(self) -> HazardKind: ...
    @property
    def street(self) -> str: ...
    @property
    def riders(self) -> int: ...
    @property
    def first_seen(self) -> date: ...
    @property
    def status(self) -> CityHazardStatus: ...


def city_alerts(
    pm25_by_weekday_hour: Sequence[Sequence[float]],
    hotspots: Sequence[AlertHotspot],
    ranking: Sequence[AlertSegment],
    hazards: Sequence[AlertHazard],
) -> list[CityAlert]:
    alerts: list[CityAlert] = []
    # sorted() is stable: on ties the first junction in the list wins, as in the web app.
    rising = next(iter(sorted(hotspots, key=lambda h: -h.trend)), None)
    if rising:
        alerts.append(
            CityAlert(
                id="rising",
                tone=AlertTone.BAD,
                title=f"Hard brakes rising at {rising.label}",
                body=f"+{js_number(rising.trend)}% vs the previous 30 days · {rising.hard_brakes_week} this week, "
                f"mostly around {_hour(rising.peak_hour)}.",
                href="/city/safety",
            )
        )
    rough = next(iter(sorted((r for r in ranking if r.surface_index < ROUGH_BELOW), key=lambda r: -r.riders30d)), None)
    if rough:
        span = f" ({rough.from_} → {rough.to})" if rough.from_ and rough.to else ""
        alerts.append(
            CityAlert(
                id="rough",
                tone=AlertTone.BAD,
                title=f"{rough.street}{span} needs resurfacing",
                body=f"Surface index {js_number(rough.surface_index)}/100 on a street {rough.riders30d:,} riders "
                f"used this month; {rough.confirmed_impacts} impacts confirmed.",
                href="/city/surface",
            )
        )
    alerts.append(_air_alert(pm25_by_weekday_hour))
    flagged = next(
        iter(sorted((h for h in hazards if h.status is CityHazardStatus.NEW), key=lambda h: -h.riders)), None
    )
    if flagged:
        alerts.append(
            CityAlert(
                id="flagged",
                tone=AlertTone.BAD,
                title=f"Riders flag {HAZARD_NOUN[flagged.kind]} on {flagged.street}",
                body=f"{flagged.riders} different riders flagged or confirmed it from their Clip "
                f"since {day_month(flagged.first_seen)}. Not yet in IRIS.",
                href="/city/safety#hazards",
            )
        )
    busy = [h for h in hotspots if h.hard_brakes_week >= EASING_MIN_PER_WEEK]
    easing = next(iter(sorted(busy, key=lambda h: h.trend)), None)
    if easing and easing.trend < 0:
        alerts.append(
            CityAlert(
                id="easing",
                tone=AlertTone.GOOD,
                title=f"Fewer hard brakes at {easing.label}",
                body=f"{js_number(easing.trend)}% vs the previous 30 days since the signal phasing changed. "
                "Keep an eye on the parallel streets.",
                href="/city/safety",
            )
        )
    return alerts


def _air_alert(pm25_by_weekday_hour: Sequence[Sequence[float]]) -> CityAlert:
    weekday, hour, peak = 0, 0, 0.0
    for d, row in enumerate(pm25_by_weekday_hour):
        for h, pm25 in enumerate(row):
            if pm25 > peak:
                weekday, hour, peak = d, h, pm25
    excess = (peak / THRESHOLDS.eu2030_pm25 - 1) * 100
    versus = f"{js_round(excess)}% above" if excess > 0 else "within"
    return CityAlert(
        id="air",
        tone=AlertTone.MID,
        title=f"PM2.5 peaks on {WEEKDAY_NAMES[weekday]}s at {_hour(hour)}",
        body=f"{peak:.1f} µg/m³ on measured streets, {versus} the EU 2030 limit.",
        href="/city/air-noise",
    )


def _hour(hour: int) -> str:
    return f"{hour:02d}:00"
