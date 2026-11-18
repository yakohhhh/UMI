"""k-anonymity rules for anything published beyond the rider's own data.

Thresholds come from protocol/constants.toml. They are applied at query time on
distinct riders, never trusted from a stored status alone (ADR 0006).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from umi_protocol import constants

from umi_api.domain.enums import BrakeCause, Period
from umi_api.domain.numbers import js_round

OTHER: Literal["other"] = "other"

# Ties keep the most common causes first, the order the web app used for its mixes.
CAUSE_ORDER = (
    BrakeCause.VEHICLE,
    BrakeCause.PEDESTRIAN,
    BrakeCause.JUNCTION,
    BrakeCause.LANE_BLOCKED,
    BrakeCause.CAR_DOOR,
    BrakeCause.SURFACE,
    BrakeCause.ANIMAL,
    BrakeCause.ROADWORKS,
)
# More named causes would make a junction's mix too easy to tie back to one answer.
MAX_NAMED_CAUSES = 4

PERIOD_DAYS: dict[Period, int] = {Period.WEEK: 7, Period.MONTH: 30, Period.QUARTER: 90, Period.YEAR: 365}

_SHARE_UNITS = js_round(1 / constants.PRIVACY_CAUSE_SHARE_ROUNDING)
_MIN_UNITS = js_round(constants.PRIVACY_CAUSE_SHARE_MIN * _SHARE_UNITS)


@dataclass(frozen=True)
class CauseShare:
    cause: BrakeCause | Literal["other"]
    share: float


def published_on_map(riders: int) -> bool:
    return riders >= constants.PRIVACY_MAP_MIN_RIDERS


def published_to_city(riders: int) -> bool:
    return riders >= constants.PRIVACY_CITY_MIN_RIDERS


def period_start(now: datetime, period: Period) -> datetime:
    return now - timedelta(days=PERIOD_DAYS[period])


def cause_mix(answers: Mapping[BrakeCause, float], riders: int) -> list[CauseShare] | None:
    """Why riders brake at a junction, safe to publish, or None below the city threshold.

    `answers` weighs each cause (answer counts); `riders` is the number of
    different riders behind them. "Just me" answers never leave the rider's ride.
    Shares are rounded to 10 %; a cause that rounds below `cause_share_min` is
    merged into "other", and so is everything after the top MAX_NAMED_CAUSES.
    """
    if not published_to_city(riders):
        return None
    weights = [(cause, answers.get(cause, 0.0)) for cause in CAUSE_ORDER]
    total = sum(weight for _, weight in weights)
    if total <= 0:
        return None
    units = [(cause, js_round(weight / total * _SHARE_UNITS)) for cause, weight in weights]
    # sorted() is stable, so equal shares keep CAUSE_ORDER.
    named = sorted((item for item in units if item[1] >= _MIN_UNITS), key=lambda item: -item[1])[:MAX_NAMED_CAUSES]
    other = _SHARE_UNITS - sum(n for _, n in named)
    if other < 0:
        # Rounding can overshoot 100 %: take it off the largest cause.
        largest, n = named[0]
        named[0] = (largest, n + other)
    mix = [CauseShare(cause=cause, share=n / _SHARE_UNITS) for cause, n in named]
    if other > 0:
        mix.append(CauseShare(cause=OTHER, share=other / _SHARE_UNITS))
    return mix
