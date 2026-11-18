"""The other riders behind the demo's city figures.

The mocks only carry totals ("23 riders flagged it", "28 riders answered here").
The backend counts distinct riders from one row each (ADR 0006), so the seed
writes those rows: pseudonymous rider keys, spread in time, some of them runs.
"""

import math
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from umi_api.domain.city import CityFilters, scale_hotspot
from umi_api.domain.enums import ActivityType, BrakeCause, Period
from umi_api.domain.numbers import js_round
from umi_api.domain.privacy import CAUSE_ORDER, PERIOD_DAYS

# Runners flag far less from a belt clip.
RUNNER_SHARE = 0.2
# About one hard brake in six gets a "why did you brake?" answer.
ANSWER_RATE = 0.16
# About one answer in twenty comes from a run.
RUN_SHARE_PERCENT = 5

# Priors of the web mock's synthetic cause mixes (withCauses in src/lib/api.ts).
CAUSE_PRIORS: dict[BrakeCause, float] = {
    BrakeCause.VEHICLE: 0.34,
    BrakeCause.PEDESTRIAN: 0.2,
    BrakeCause.JUNCTION: 0.14,
    BrakeCause.LANE_BLOCKED: 0.12,
    BrakeCause.CAR_DOOR: 0.07,
    BrakeCause.SURFACE: 0.06,
    BrakeCause.ANIMAL: 0.04,
    BrakeCause.ROADWORKS: 0.03,
}
# Verdaguer has a dog-walking promenade on Pg. de Sant Joan: the "dog" brakes are a real pattern there.
KNOWN_MIXES: dict[str, dict[BrakeCause, float]] = {
    "hs-1": {
        BrakeCause.VEHICLE: 0.4,
        BrakeCause.PEDESTRIAN: 0.2,
        BrakeCause.JUNCTION: 0.2,
        BrakeCause.ANIMAL: 0.1,
        # Small causes the published mix merges into "other".
        BrakeCause.CAR_DOOR: 0.05,
        BrakeCause.ROADWORKS: 0.05,
    }
}


@dataclass(frozen=True)
class PanelRider:
    key: str
    activity_type: ActivityType
    at: datetime


@dataclass(frozen=True)
class PanelAnswer:
    rider: PanelRider
    cause: BrakeCause


def runners(riders: int) -> int:
    return js_round(riders * RUNNER_SHARE)


def spread(start: datetime, end: datetime, count: int) -> list[datetime]:
    """`count` instants from `start` to `end` inclusive, evenly spaced."""
    if count == 1:
        return [start]
    step = (end - start) / (count - 1)
    return [start + step * i for i in range(count)]


def hazard_riders(hazard_id: str, times: list[datetime], *, runs: int) -> list[PanelRider]:
    """One rider per instant; the last `runs` of them on foot."""
    return [
        PanelRider(
            key=f"panel-{hazard_id}-{i:02d}",
            activity_type=ActivityType.RUN if i >= len(times) - runs else ActivityType.RIDE,
            at=at,
        )
        for i, at in enumerate(times)
    ]


def cause_weights(hotspot_id: str) -> Mapping[BrakeCause, float]:
    """The web mock's mix for a hotspot: priors perturbed by a seed taken from its id."""
    if hotspot_id in KNOWN_MIXES:
        return KNOWN_MIXES[hotspot_id]
    seed = int("".join(c for c in hotspot_id if c.isdigit()) or 0)
    return {cause: w * (1 + 0.6 * math.sin(seed * 1.7 + k * 2.3)) for k, (cause, w) in enumerate(CAUSE_PRIORS.items())}


def answers_in(period: Period, hard_brakes30d: int) -> int:
    """Riders who answered at a hotspot over a period, as the web mock derived them."""
    brakes, _ = scale_hotspot(hard_brakes30d, 0, CityFilters(period=period))
    return js_round(brakes * ANSWER_RATE)


def hotspot_answers(hotspot_id: str, hard_brakes30d: int, now: datetime) -> list[PanelAnswer]:
    """A year of answers at a hotspot, newest first, one distinct rider each.

    Causes follow a house-monotone apportionment (Webster), so every window
    (7, 30, 90, 365 days) has the hotspot's mix whatever its size.
    """
    periods = sorted(Period, key=lambda p: PERIOD_DAYS[p])
    totals = [answers_in(p, hard_brakes30d) for p in periods]
    causes = _webster(cause_weights(hotspot_id), totals[-1])
    answers: list[PanelAnswer] = []
    newer, done = now, 0
    for period, total in zip(periods, totals, strict=True):
        older = now - timedelta(days=PERIOD_DAYS[period])
        count = total - done
        for j in range(count):
            # Strictly inside the window, never on its edge.
            at = newer - (newer - older) * ((j + 0.5) / count)
            key = f"panel-{hotspot_id}-{done + j:04d}"
            answers.append(PanelAnswer(PanelRider(key, _activity_of(key), at), causes[done + j]))
        newer, done = older, total
    return answers


def _activity_of(rider_key: str) -> ActivityType:
    """Runs picked by a hash of the rider, so they don't line up with the cause sequence."""
    return ActivityType.RUN if zlib.crc32(rider_key.encode()) % 100 < RUN_SHARE_PERCENT else ActivityType.RIDE


def _webster(weights: Mapping[BrakeCause, float], count: int) -> list[BrakeCause]:
    """Causes in draw order: each next answer goes to the most under-represented cause."""
    order = [c for c in CAUSE_ORDER if c in weights]
    tally = dict.fromkeys(order, 0)
    drawn = []
    for _ in range(count):
        cause = max(order, key=lambda c: weights[c] / (tally[c] + 0.5))
        tally[cause] += 1
        drawn.append(cause)
    return drawn
