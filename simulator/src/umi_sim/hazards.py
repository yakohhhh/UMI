"""The rider's thumb on the flag button: which hazards they flag, and how.

Riding past a hazard (one other riders flagged, a confirmed pothole, a hotspot
where people brake hard), a rider presses with a probability that depends on
them and on how striking the hazard is. Riders who turned voice keywords on
(opt-in, a minority) usually hold the button and say the word instead. Now and
then a press is a slip of the thumb, undone with a double press, or a rider
changes their mind about a flag.

These are gestures with the rider's intent. What the Clip makes of them (FLAG,
FLAG_UNDO, the keyword threshold) is decided in ``clip.py``; what the keyword
recogniser hears is decided in ``sensors.py``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum

from umi_protocol import HazardKind, Lang
from umi_protocol.constants import BUTTON_DOUBLE_PRESS_GAP_MS, BUTTON_HOLD_MS, BUTTON_VOICE_WINDOW_MS

from .network import Route
from .rider import Trajectory
from .world import Severity, World

_HAZARD_REACH_M = 20.0
_HOTSPOT_REACH_M = 25.0
_SALIENCE: dict[HazardKind, float] = {
    HazardKind.ROADWORKS: 0.7,
    HazardKind.BLOCKED_LANE: 0.6,
    HazardKind.OBSTACLE: 0.6,
    HazardKind.POTHOLE: 0.5,
    HazardKind.DANGER: 0.4,
}
_POTHOLE_SALIENCE: dict[Severity, float] = {"high": 0.45, "medium": 0.3, "low": 0.2}
# A hotspot is rarely flagged as such: riders brake there, they do not stop to report it.
_HOTSPOT_SALIENCE = 0.08
_HOLD_P = 0.75
_SILENT_HOLD_P = 0.05
_SLIP_P = 0.06
_SLIP_UNDONE_P = 0.85
_CHANGE_MIND_P = 0.04


class GestureKind(StrEnum):
    PRESS = "press"
    HOLD = "hold"
    DOUBLE = "double"


# A gesture occupies the button until the Clip has decided it: the double-press
# gap after a press, the voice window after a hold.
_BUSY_S = {
    GestureKind.PRESS: (BUTTON_DOUBLE_PRESS_GAP_MS + 500) / 1000,
    GestureKind.HOLD: (BUTTON_HOLD_MS + BUTTON_VOICE_WINDOW_MS + 500) / 1000,
    GestureKind.DOUBLE: (BUTTON_DOUBLE_PRESS_GAP_MS + 500) / 1000,
}


@dataclass(frozen=True, slots=True)
class FlagHabits:
    """How a rider uses the button."""

    propensity: float = 0.5
    voice: bool = False
    lang: Lang = Lang.CA


@dataclass(frozen=True, slots=True)
class Gesture:
    """What the rider does with the button, dated at the first press (ride time, seconds).

    ``said`` is the keyword spoken during a hold (``None``: the rider said nothing).
    """

    kind: GestureKind
    t: float
    said: HazardKind | None = None


@dataclass(frozen=True, slots=True)
class Sighting:
    """A hazard the route passes, ``s`` metres in."""

    s: float
    kind: HazardKind
    salience: float


def sightings(route: Route, world: World) -> list[Sighting]:
    found = []
    for hazard in world.hazards:
        if (s := route.locate(hazard.position, _HAZARD_REACH_M)) is not None:
            found.append(Sighting(s, hazard.kind, _SALIENCE.get(hazard.kind, 0.5)))
    for pothole in world.potholes:
        if (s := route.locate(pothole.position, _HAZARD_REACH_M)) is not None:
            found.append(Sighting(s, HazardKind.POTHOLE, _POTHOLE_SALIENCE[pothole.severity]))
    for hotspot in world.hotspots:
        if (s := route.locate(hotspot.position, _HOTSPOT_REACH_M)) is not None:
            found.append(Sighting(s, HazardKind.DANGER, _HOTSPOT_SALIENCE))
    return sorted(found, key=lambda sighting: sighting.s)


def plan_gestures(
    route: Route, trajectory: Trajectory, world: World, habits: FlagHabits, rng: random.Random
) -> list[Gesture]:
    """The rider's button gestures during the ride, in time order, never overlapping."""
    gestures: list[Gesture] = []
    for sighting in sightings(route, world):
        if rng.random() >= habits.propensity * sighting.salience:
            continue
        # Pressed just after passing it, once the rider has seen what it was.
        t = trajectory.time_at(sighting.s) + rng.uniform(0.5, 4.0)
        if habits.voice and rng.random() < _HOLD_P:
            said = None if rng.random() < _SILENT_HOLD_P else sighting.kind
            gestures.append(Gesture(GestureKind.HOLD, t, said))
        else:
            gestures.append(Gesture(GestureKind.PRESS, t))
        if rng.random() < _CHANGE_MIND_P:
            gestures.append(Gesture(GestureKind.DOUBLE, t + _BUSY_S[gestures[-1].kind] + rng.uniform(1.0, 6.0)))
    if trajectory.arrival > 180.0 and rng.random() < _SLIP_P:
        t = rng.uniform(60.0, trajectory.arrival - 60.0)
        gestures.append(Gesture(GestureKind.PRESS, t))
        if rng.random() < _SLIP_UNDONE_P:
            gestures.append(Gesture(GestureKind.DOUBLE, t + _BUSY_S[GestureKind.PRESS] + rng.uniform(0.5, 3.0)))
    return _without_overlaps(sorted(gestures, key=lambda g: g.t))


def _without_overlaps(gestures: list[Gesture]) -> list[Gesture]:
    """Drop gestures that start while the button is still busy with the previous one."""
    kept: list[Gesture] = []
    for gesture in gestures:
        if not kept or gesture.t >= kept[-1].t + _BUSY_S[kept[-1].kind]:
            kept.append(gesture)
    return kept
