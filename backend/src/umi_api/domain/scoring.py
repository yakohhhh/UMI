"""Street scores (port of src/lib/score.ts).

Each street segment has four hourly scores (0-100) computed from the sensors:
vibration -> comfort, hard brakes -> safety, PM2.5 -> air, dB(A) -> noise.
"""

from enum import StrEnum
from typing import Protocol

from umi_api.domain.numbers import js_round

GOOD_FROM = 70
MID_FROM = 45


class ScoreBand(StrEnum):
    GOOD = "good"
    MID = "mid"
    BAD = "bad"


class ScoreSet(Protocol):
    @property
    def comfort(self) -> int: ...
    @property
    def safety(self) -> int: ...
    @property
    def air(self) -> int: ...
    @property
    def noise(self) -> int: ...


def score_band(score: float) -> ScoreBand:
    if score >= GOOD_FROM:
        return ScoreBand.GOOD
    if score >= MID_FROM:
        return ScoreBand.MID
    return ScoreBand.BAD


def overall_score(scores: ScoreSet) -> int:
    """A street is only as calm as its worst aspect.

    The weighted mean (comfort and safety weigh a bit more for riders) is pulled
    toward the weakest dimension, then calibrated so 50 sits at the city's
    rush-hour median, the same spread as the four sub-scores.
    """
    values = (scores.comfort, scores.safety, scores.air, scores.noise)
    mean = scores.comfort * 0.3 + scores.safety * 0.3 + scores.air * 0.2 + scores.noise * 0.2
    raw = 0.55 * mean + 0.45 * min(values)
    v = 50 + (raw - 52) * 1.5
    # Soft knees keep the extremes believable (no street is a perfect 100).
    if v > 80:
        v = 80 + (v - 80) * 0.5
    elif v < 20:
        v = 20 - (20 - v) * 0.5
    return _clamp(js_round(v))


# Sensor conversions, kept in sync with scripts/generate-mock-data.mjs.
def air_score_from_pm(pm25: float) -> int:
    return _clamp(js_round(100 - (pm25 - 5) * 3.2))


def noise_score_from_db(db: float) -> int:
    return _clamp(js_round(100 - (db - 50) * 3.3))


def comfort_score_from_vib(vib_rms: float) -> int:
    return _clamp(js_round(100 - (vib_rms - 0.4) * 38))


def brakes_from_safety_score(score: float) -> int:
    """Hard brakes (> 3 m/s²) per 100 passes implied by a safety score."""
    return max(0, js_round((100 - score) / 4.5))


def safety_score_from_brakes(per_100_passes: float) -> int:
    """Safety score of a street from its hard brakes per 100 passes (inverse of brakes_from_safety_score)."""
    return _clamp(js_round(100 - per_100_passes * 4.5))


# One hard brake costs a ride this many safety points (scoreRide in scripts/generate-mock-data.mjs).
RIDE_BRAKE_PENALTY = 9


def ride_safety_score(street_safety: float, hard_brakes: int) -> int:
    """How safe a ride was: the streets it took at that hour, minus what happened on them."""
    return _clamp(js_round(street_safety - RIDE_BRAKE_PENALTY * hard_brakes))


def pass_score(comfort: float, air: float, noise: float) -> int:
    """One pass through a street, as a ride report compares it with the street's own score.

    Same blend as routeSegments in scripts/generate-mock-data.mjs. Safety is left
    out: a single pass says little about how often riders brake there.
    """
    return js_round(comfort * 0.35 + air * 0.35 + noise * 0.3)


def _clamp(value: int) -> int:
    return max(0, min(100, value))
