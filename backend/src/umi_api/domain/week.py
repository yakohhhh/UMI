"""The rider's current week, Monday first, in Barcelona time."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from umi_api.domain.calendar import local_day, local_weekday
from umi_api.domain.enums import ActivityType
from umi_api.domain.numbers import js_round

DAY_LABELS = ("M", "T", "W", "T", "F", "S", "S")


class WeekActivity(Protocol):
    @property
    def type(self) -> ActivityType: ...
    @property
    def started_at(self) -> datetime: ...
    @property
    def distance_m(self) -> int: ...
    @property
    def moving_time_s(self) -> int: ...


@dataclass(frozen=True)
class DayDistance:
    label: str
    km: float
    is_today: bool


@dataclass(frozen=True)
class WeekSummary:
    distance_km: float
    moving_time_s: int
    rides: int
    runs: int
    days: list[DayDistance]


def week_summary(activities: Sequence[WeekActivity], now: datetime) -> WeekSummary:
    today = local_weekday(now)
    monday = local_day(now - timedelta(days=today))
    week = [a for a in activities if local_day(a.started_at) >= monday]
    days = [
        DayDistance(
            label=label,
            km=_km(sum(a.distance_m for a in week if local_weekday(a.started_at) == index)),
            is_today=index == today,
        )
        for index, label in enumerate(DAY_LABELS)
    ]
    return WeekSummary(
        distance_km=_km(sum(a.distance_m for a in week)),
        moving_time_s=sum(a.moving_time_s for a in week),
        rides=sum(1 for a in week if a.type is ActivityType.RIDE),
        runs=sum(1 for a in week if a.type is ActivityType.RUN),
        days=days,
    )


def _km(meters: float) -> float:
    return js_round(meters / 100) / 10
