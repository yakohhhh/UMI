"""Stage 8: what the ride adds to the rider's exposure that Barcelona day."""

from dataclasses import dataclass
from datetime import date
from statistics import fmean
from typing import Protocol

from umi_api.domain.calendar import local_day
from umi_api.domain.numbers import js_round, round_to
from umi_api.pipeline.readings import Readings
from umi_api.pipeline.track import Track


class StoredDay(Protocol):
    @property
    def ride_min(self) -> int: ...
    @property
    def pm25(self) -> float | None: ...
    @property
    def db(self) -> float | None: ...
    @property
    def dose_ug_h(self) -> float: ...


@dataclass(frozen=True)
class ExposureDayValues:
    day: date
    ride_min: int
    # Riding-time-weighted means.
    pm25: float | None
    db: float | None
    dose_ug_h: float


def ride_exposure(track: Track, readings: Readings, moving_time_s: int) -> ExposureDayValues:
    minutes = max(1, js_round(moving_time_s / 60))
    pm25 = fmean(readings.pm25)
    return ExposureDayValues(
        day=local_day(track.started_at),
        ride_min=minutes,
        pm25=round_to(pm25, 1),
        db=round_to(fmean(readings.db), 1),
        dose_ug_h=round_to(pm25 * minutes / 60, 1),
    )


def add_exposure(stored: StoredDay | None, ride: ExposureDayValues) -> ExposureDayValues:
    """The day with the ride added to what was already stored for it."""
    if stored is None:
        return ride
    minutes = stored.ride_min + ride.ride_min
    return ExposureDayValues(
        day=ride.day,
        ride_min=minutes,
        pm25=_weighted(stored.pm25, stored.ride_min, ride.pm25, ride.ride_min),
        db=_weighted(stored.db, stored.ride_min, ride.db, ride.ride_min),
        dose_ug_h=round_to(stored.dose_ug_h + ride.dose_ug_h, 1),
    )


def _weighted(a: float | None, a_min: int, b: float | None, b_min: int) -> float | None:
    parts = [(value, minutes) for value, minutes in ((a, a_min), (b, b_min)) if value is not None and minutes > 0]
    total = sum(minutes for _, minutes in parts)
    return round_to(sum(value * minutes for value, minutes in parts) / total, 1) if total else None
