"""Route alternatives forecast for a departure hour."""

from dataclasses import dataclass
from typing import Protocol

from umi_api.domain.numbers import js_round

# Weekday traffic intensity by hour (0..1), the same profile as the street scores.
TRAFFIC = (
    0.16, 0.1, 0.07, 0.07, 0.11, 0.24, 0.52, 0.86, 1.0, 0.88, 0.74, 0.7,
    0.73, 0.77, 0.72, 0.7, 0.76, 0.86, 0.95, 0.88, 0.68, 0.5, 0.36, 0.24,
)  # fmt: skip
# Stored alternatives are computed for the 08:00 peak.
BASE_HOUR = 8


class RouteAtPeak(Protocol):
    @property
    def duration_min(self) -> int: ...
    @property
    def comfort(self) -> int: ...
    @property
    def safety(self) -> int: ...
    @property
    def air(self) -> int: ...
    @property
    def noise(self) -> int: ...


@dataclass(frozen=True)
class RouteForecast:
    duration_min: int
    comfort: int
    safety: int
    air: int
    noise: int


def departure_hour(depart_at: str | None) -> int:
    """Hour of an "HH:MM" departure (validated by the request schema); the peak hour when missing."""
    return BASE_HOUR if depart_at is None else int(depart_at[:2])


def forecast(route: RouteAtPeak, hour: int) -> RouteForecast:
    """Lighter traffic than at the peak means calmer, cleaner, faster streets."""
    calm = 1 - TRAFFIC[hour]

    def bump(value: int, gain: float) -> int:
        return max(0, min(100, js_round(value + gain * calm)))

    return RouteForecast(
        duration_min=max(1, js_round(route.duration_min * (0.85 + 0.15 * TRAFFIC[hour]))),
        comfort=bump(route.comfort, 3),
        safety=bump(route.safety, 14),
        air=bump(route.air, 16),
        noise=bump(route.noise, 22),
    )
