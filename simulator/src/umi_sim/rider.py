"""Virtual riders: how fast they go, where they slow down, stop and brake hard.

The ride is a speed profile over the route, planned the way vehicle motion
usually is: a speed limit at every point (cruising pace of the street, junction
slow-downs, red lights, hard brakes, the destination), one forward pass that
respects the rider's acceleration and one backward pass that respects their
braking. Between profile points the acceleration is constant, so position and
speed at any instant are exact, and a stop is a pair of points with the same
position.

Hard brakes are where the backward pass is allowed to brake harder than the
comfortable rate: on a few junctions, more often near the hotspots of
``hotspots.json`` and on streets with a poor safety score. Everything is drawn
from the ``random.Random`` passed in, so a seed gives the same ride every time.
"""

from __future__ import annotations

import math
import random
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from umi_protocol import Activity

from .network import Route
from .scores import brakes_from_safety_score
from .world import Hotspot, StreetKind

KMH = 1 / 3.6

# Planning resolution along the route (metres).
_STEP_M = 2.0
# How far the cruising pace drifts (relative), and over what distance.
_PACE_DRIFT = 0.05
_PACE_CHUNK_M = 80.0
_RED_LIGHT_P = 0.42
_RED_WAIT_S = (3.0, 40.0)
# Now and then a rider stops a while mid-ride (a shop, a phone call): long
# enough for the Clip to auto-pause.
_ERRAND_P = 0.05
_ERRAND_WAIT_S = (45.0, 150.0)
_HOTSPOT_REACH_M = 25.0
_FULL_STOP_P = 0.25
_TURN_DEG = 45.0
_U_TURN_DEG = 150.0


class Vehicle(StrEnum):
    E_BIKE = "e-bike"
    BIKE = "bike"
    SCOOTER = "scooter"
    RUN = "run"

    @property
    def activity(self) -> Activity:
        return Activity.RUN if self is Vehicle.RUN else Activity.RIDE


@dataclass(frozen=True, slots=True)
class Dynamics:
    """How one kind of rider moves (speeds in km/h, accelerations in m/s²)."""

    cruise_kmh: float
    max_kmh: float
    accel: float
    decel: float
    junction_kmh: float
    turn_kmh: float
    hard_brake: tuple[float, float]
    # Scales the hard brakes the safety scores imply; runners do not brake hard.
    brake_rate: float


DYNAMICS: dict[Vehicle, Dynamics] = {
    # Assistance stops at 25 km/h (EU pedelec); scooters are capped at 25 km/h in Spain.
    Vehicle.E_BIKE: Dynamics(22.0, 25.0, 1.1, 1.8, 14.0, 10.0, (3.2, 5.0), 1.0),
    Vehicle.BIKE: Dynamics(18.0, 30.0, 0.8, 1.6, 13.0, 9.5, (3.2, 4.8), 1.0),
    Vehicle.SCOOTER: Dynamics(19.0, 25.0, 1.0, 1.8, 12.0, 9.0, (3.3, 5.5), 1.2),
    Vehicle.RUN: Dynamics(10.5, 16.0, 0.6, 1.0, 9.5, 8.0, (0.0, 0.0), 0.0),
}

# Riders ease off where the street is shared or has no lane; runners keep their pace.
_STREET_PACE: dict[StreetKind, float] = {
    "arterial": 0.95,
    "boulevard": 1.0,
    "street": 0.97,
    "green": 0.9,
    "promenade": 0.75,
    "seafront": 0.95,
}


@dataclass(frozen=True, slots=True)
class Knot:
    """A profile point; the acceleration is constant until the next one."""

    t: float
    s: float
    v: float


@dataclass(frozen=True, slots=True)
class Deceleration:
    """A stretch of braking above some rate: start time, duration, mean deceleration (m/s²)."""

    t: float
    duration: float
    mean: float


@dataclass(frozen=True, slots=True)
class MotionState:
    s: float
    v: float
    a: float


class Trajectory:
    """Where the rider is along the route at any time; ``t = 0`` is the departure, at rest."""

    def __init__(self, knots: Sequence[Knot]) -> None:
        self.knots = tuple(knots)
        self._t = [k.t for k in self.knots]
        self._s = [k.s for k in self.knots]

    @property
    def arrival(self) -> float:
        return self.knots[-1].t

    @property
    def length(self) -> float:
        return self.knots[-1].s

    def state_at(self, t: float) -> MotionState:
        """Position, speed and acceleration at ``t``; at rest before departure and after arrival."""
        if t <= 0.0:
            return MotionState(0.0, 0.0, 0.0)
        if t >= self.arrival:
            return MotionState(self.length, 0.0, 0.0)
        i = bisect_right(self._t, t) - 1
        k0, k1 = self.knots[i], self.knots[i + 1]
        a = (k1.v - k0.v) / (k1.t - k0.t)
        tau = t - k0.t
        return MotionState(k0.s + k0.v * tau + 0.5 * a * tau * tau, k0.v + a * tau, a)

    def time_at(self, s: float) -> float:
        """When the rider first reaches distance ``s``."""
        if s <= 0.0:
            return 0.0
        if s >= self.length:
            return self.arrival
        # The first knot at or past s: at a stop, the arrival rather than the departure.
        j = bisect_left(self._s, s)
        k0, k1 = self.knots[j - 1], self.knots[j]
        if k1.s == s:
            return k1.t
        a = (k1.v - k0.v) / (k1.t - k0.t)
        ds = s - k0.s
        tau = ds / k0.v if abs(a) < 1e-9 else (math.sqrt(max(k0.v * k0.v + 2 * a * ds, 0.0)) - k0.v) / a
        return k0.t + tau

    def decelerations(self, above: float) -> list[Deceleration]:
        """Stretches where the rider slowed down faster than ``above`` m/s²."""
        phases: list[Deceleration] = []
        start: Knot | None = None
        for k0, k1 in pairwise(self.knots):
            braking = k1.t > k0.t and (k0.v - k1.v) / (k1.t - k0.t) > above
            if braking and start is None:
                start = k0
            elif not braking and start is not None:
                phases.append(_deceleration(start, k0))
                start = None
        if start is not None:
            phases.append(_deceleration(start, self.knots[-1]))
        return phases


def _deceleration(start: Knot, end: Knot) -> Deceleration:
    duration = end.t - start.t
    return Deceleration(start.t, duration, (start.v - end.v) / duration)


@dataclass(frozen=True, slots=True)
class _Limit:
    """At most ``speed`` (m/s) at ``s``, reached braking at ``decel``; a stop waits ``dwell`` seconds."""

    s: float
    speed: float
    decel: float
    dwell: float = 0.0


def ride(
    route: Route,
    vehicle: Vehicle,
    rng: random.Random,
    *,
    hour: int,
    hotspots: Sequence[Hotspot] = (),
    pace: float = 1.0,
) -> Trajectory:
    """Plan one ride along ``route`` at local ``hour``; ``pace`` is the rider's own speed factor."""
    dyn = DYNAMICS[vehicle]
    cruise = _cruise(route, vehicle, dyn, rng, pace)
    limits = [
        *_junction_limits(route, dyn, rng),
        *_hard_brakes(route, dyn, rng, hour=hour, hotspots=hotspots, cruise=cruise),
    ]
    return Trajectory(_profile(route.length, cruise, limits, dyn))


def _cruise(route: Route, vehicle: Vehicle, dyn: Dynamics, rng: random.Random, pace: float) -> Callable[[float], float]:
    """Cruising speed along the route: the rider's pace, the street, and a slow drift."""
    drift = [rng.gauss(1.0, _PACE_DRIFT) for _ in range(int(route.length // _PACE_CHUNK_M) + 2)]
    base = dyn.cruise_kmh * KMH * pace
    cap = dyn.max_kmh * KMH

    def at(s: float) -> float:
        street = route.street_at(s)
        factor = 1.0 if vehicle is Vehicle.RUN else _STREET_PACE[street.kind] * (1.03 if street.bike_lane else 1.0)
        x = s / _PACE_CHUNK_M
        i = int(x)
        wobble = drift[i] + (drift[i + 1] - drift[i]) * (x - i)
        return min(base * factor * wobble, cap)

    return at


def _junction_limits(route: Route, dyn: Dynamics, rng: random.Random) -> list[_Limit]:
    limits = []
    middle = [j for j in route.junctions if route.length * 0.25 < j.s < route.length * 0.75]
    errand = rng.choice(middle) if middle and rng.random() < _ERRAND_P else None
    for junction in route.junctions:
        if junction is errand:
            limits.append(_Limit(junction.s, 0.0, dyn.decel, rng.uniform(*_ERRAND_WAIT_S)))
        elif junction.has_lights and rng.random() < _RED_LIGHT_P:
            limits.append(_Limit(junction.s, 0.0, dyn.decel, rng.uniform(*_RED_WAIT_S)))
        else:
            turn = abs(junction.turn_deg)
            kmh = 5.0 if turn > _U_TURN_DEG else dyn.turn_kmh if turn > _TURN_DEG else dyn.junction_kmh
            limits.append(_Limit(junction.s, kmh * KMH, dyn.decel))
    return limits


def _hard_brakes(
    route: Route,
    dyn: Dynamics,
    rng: random.Random,
    *,
    hour: int,
    hotspots: Sequence[Hotspot],
    cruise: Callable[[float], float],
) -> list[_Limit]:
    """Where the rider brakes hard: near busy hotspots, and as often as the streets' safety scores imply."""
    if dyn.brake_rate == 0.0:
        return []
    spots: list[tuple[float, float | None]] = []  # (position, typical deceleration there)
    for hotspot in hotspots:
        s = route.locate(hotspot.position, _HOTSPOT_REACH_M)
        peak = 1.4 if abs(hour - hotspot.peak_hour) <= 1 else 1.0
        p = min(0.5, 0.012 * hotspot.hard_brakes_week * peak) * dyn.brake_rate
        if s is not None and rng.random() < p:
            spots.append((s - rng.uniform(3.0, 15.0), hotspot.avg_decel_mps2))
    for step in route.steps:
        street = step.edge.street
        # The safety score gives brakes per pass of the whole segment; a step may cover part of it.
        share = min(step.edge.length / street.length_m, 1.0)
        p = brakes_from_safety_score(street.scores_at(hour).safety) / 100 * dyn.brake_rate * share
        if rng.random() < p:
            spots.append((step.start_s + rng.uniform(0.2, 0.9) * step.edge.length, None))

    lo, hi = dyn.hard_brake
    limits = []
    for s, typical in spots:
        if not 30.0 < s < route.length - 30.0:
            continue
        decel = rng.uniform(lo, hi) if typical is None else min(max(rng.gauss(typical, 0.4), lo), hi)
        if rng.random() < _FULL_STOP_P:
            limits.append(_Limit(s, 0.0, decel, rng.uniform(1.0, 4.0)))
        else:
            limits.append(_Limit(s, cruise(s) * rng.uniform(0.1, 0.55), decel))
    return limits


def _profile(length: float, cruise: Callable[[float], float], limits: Sequence[_Limit], dyn: Dynamics) -> list[Knot]:
    n = max(2, math.ceil(length / _STEP_M))
    step = length / n
    vmax = [cruise(k * step) for k in range(n + 1)]
    decel = [dyn.decel] * n  # per interval k → k + 1
    dwell = [0.0] * (n + 1)
    stops = {0, n}
    top = max(vmax)
    for limit in sorted(limits, key=lambda lim: lim.s):
        k = min(max(round(limit.s / step), 1), n - 1)
        if limit.speed == 0.0:
            # A stop next to another one is the same stop: two standstills a step
            # apart would leave the rider no way to cover that step.
            near = next((z for z in stops if abs(z - k) <= 1), None)
            if near is not None:
                dwell[near] += limit.dwell
                continue
            stops.add(k)
            dwell[k] = limit.dwell
        vmax[k] = min(vmax[k], limit.speed)
        if limit.decel > dyn.decel:
            reach = (top * top - limit.speed * limit.speed) / (2 * limit.decel)
            for j in range(max(0, k - math.ceil(reach / step)), k):
                decel[j] = max(decel[j], limit.decel)
    vmax[0] = vmax[n] = 0.0

    v = vmax[:]
    for k in range(1, n + 1):
        v[k] = min(v[k], math.sqrt(v[k - 1] ** 2 + 2 * dyn.accel * step))
    for k in range(n - 1, -1, -1):
        v[k] = min(v[k], math.sqrt(v[k + 1] ** 2 + 2 * decel[k] * step))

    knots = [Knot(0.0, 0.0, 0.0)]
    t = 0.0
    for k in range(1, n + 1):
        t += 2 * step / (v[k - 1] + v[k])
        knots.append(Knot(t, k * step, v[k]))
        if dwell[k] and k < n:
            t += dwell[k]
            knots.append(Knot(t, k * step, 0.0))
    return knots
