"""Score ↔ measurement conversions, ported from ``src/lib/score.ts``.

The mock street data stores hourly scores; the simulated sensors need the
measurements behind them. These are the web app's own inverse conversions, so a
simulated ride measures what the street map shows. Keep them in step with
``score.ts`` (and ``scripts/generate-mock-data.mjs``) if either changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _js_round(value: float) -> int:
    """``Math.round``: halves go up, unlike Python's banker's rounding."""
    return math.floor(value + 0.5)


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def pm_from_air_score(score: float) -> float:
    """PM2.5 in µg/m³ behind an air score (``pmFromAirScore``)."""
    return _js_round((5 + (100 - score) / 3.2) * 10) / 10


def db_from_noise_score(score: float) -> float:
    """Sound level in dB(A) behind a noise score (``dbFromNoiseScore``)."""
    return float(_js_round(50 + (100 - score) / 3.3))


def brakes_from_safety_score(score: float) -> float:
    """Hard brakes (> 3 m/s²) per 100 passes implied by a safety score (``brakesFromSafetyScore``)."""
    return float(max(0, _js_round((100 - score) / 4.5)))


@dataclass(frozen=True, slots=True)
class Scores:
    comfort: float
    safety: float
    air: float
    noise: float

    @property
    def overall(self) -> int:
        """``overallScore``: weighted mean pulled toward the weakest dimension, 50 = rush-hour median."""
        mean = self.comfort * 0.3 + self.safety * 0.3 + self.air * 0.2 + self.noise * 0.2
        weakest = min(self.comfort, self.safety, self.air, self.noise)
        v = 50 + (0.55 * mean + 0.45 * weakest - 52) * 1.5
        kneed = 80 + (v - 80) * 0.5 if v > 80 else 20 - (20 - v) * 0.5 if v < 20 else v
        return int(_clamp_score(_js_round(kneed)))
