"""Street scores per segment and hour of the day, recomputed from riders' passes.

The seeded baseline stands for the passes the database has no rows for (the
demo's history). New passes are merged into it, and a segment-hour moves away
from its baseline only once enough distinct riders passed there
(`[privacy] segment_hour_min_riders`): fewer riders could be told apart.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from statistics import fmean
from typing import Protocol

from umi_protocol import constants

from umi_api.domain.enums import ActivityType
from umi_api.domain.numbers import js_round
from umi_api.domain.scoring import (
    air_score_from_pm,
    comfort_score_from_vib,
    noise_score_from_db,
    safety_score_from_brakes,
)

MIN_RIDERS = constants.PRIVACY_SEGMENT_HOUR_MIN_RIDERS
# Passes older than this no longer describe the street (same horizon as `passes30d`).
WINDOW = timedelta(days=30)
# The baseline weighs as much as this many passes: ten new passes move a score halfway.
BASELINE_PASSES = 10


class PassLike(Protocol):
    @property
    def athlete_id(self) -> str: ...
    @property
    def activity_type(self) -> ActivityType: ...
    @property
    def vib_rms(self) -> float | None: ...
    @property
    def pm25(self) -> float | None: ...
    @property
    def db(self) -> float | None: ...
    @property
    def weighted_brakes(self) -> float: ...


@dataclass(frozen=True)
class HourScores:
    comfort: int
    safety: int
    air: int
    noise: int


def segment_hour_scores(baseline: HourScores, passes: Sequence[PassLike]) -> HourScores | None:
    """Scores to publish for one segment-hour, or None to keep the baseline (too few riders).

    Comfort and safety come from rides only: a runner's IMU measures strides, not
    the surface, and runners do not brake hard. A dimension nobody measured keeps
    its baseline.
    """
    if len({p.athlete_id for p in passes}) < MIN_RIDERS:
        return None
    rides = [p for p in passes if p.activity_type is ActivityType.RIDE]
    vib = [p.vib_rms for p in rides if p.vib_rms is not None]
    pm = [p.pm25 for p in passes if p.pm25 is not None]
    db = [p.db for p in passes if p.db is not None]
    brakes_per_100 = 100 * sum(p.weighted_brakes for p in rides) / len(rides) if rides else 0.0
    return HourScores(
        comfort=_merge(baseline.comfort, comfort_score_from_vib(fmean(vib)) if vib else None, len(vib)),
        safety=_merge(baseline.safety, safety_score_from_brakes(brakes_per_100) if rides else None, len(rides)),
        air=_merge(baseline.air, air_score_from_pm(fmean(pm)) if pm else None, len(pm)),
        noise=_merge(baseline.noise, noise_score_from_db(fmean(db)) if db else None, len(db)),
    )


def day_scores(hours: Sequence[HourScores]) -> HourScores:
    """A street's all-day scores: the rounded mean of its hours (scripts/generate-mock-data.mjs)."""
    return HourScores(
        comfort=js_round(fmean(h.comfort for h in hours)),
        safety=js_round(fmean(h.safety for h in hours)),
        air=js_round(fmean(h.air for h in hours)),
        noise=js_round(fmean(h.noise for h in hours)),
    )


def _merge(baseline: int, measured: int | None, passes: int) -> int:
    if measured is None:
        return baseline
    return js_round((baseline * BASELINE_PASSES + measured * passes) / (BASELINE_PASSES + passes))
