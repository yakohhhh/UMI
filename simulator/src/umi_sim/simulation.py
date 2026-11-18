"""One simulated ride, end to end: route → rider → button → sensors.

Each stage draws from its own random stream derived from the ride's seed, so a
change in how one stage uses randomness does not reshuffle the others, and a
seed always gives the same ride.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .geo import XY
from .hazards import FlagHabits, Gesture, plan_gestures
from .network import Route, RouteGoal, StreetNetwork
from .rider import Trajectory, Vehicle, ride
from .sensors import Readings, Weather, measure
from .world import World, load_world

#: Times on the wire are UTC; riders live by the clock in Barcelona.
LOCAL_TZ = ZoneInfo("Europe/Madrid")


@dataclass(frozen=True)
class City:
    """The datasets and the street graph built from them."""

    world: World
    network: StreetNetwork

    @classmethod
    def load(cls, data_dir: Path | None = None) -> City:
        world = load_world(data_dir)
        return cls(world, StreetNetwork.build(world.streets))


@dataclass(frozen=True, slots=True)
class RideSpec:
    """Everything that defines a ride. ``depart`` is timezone-aware; seconds are kept, microseconds dropped."""

    waypoints: tuple[XY, ...]
    depart: datetime
    vehicle: Vehicle
    seed: int
    goal: RouteGoal = RouteGoal.FASTEST
    habits: FlagHabits = field(default_factory=FlagHabits)
    pace: float = 1.0
    battery_pct: float = 90.0

    def __post_init__(self) -> None:
        if self.depart.tzinfo is None:
            raise ValueError("RideSpec.depart must be timezone-aware")


@dataclass(frozen=True)
class SimulatedRide:
    spec: RideSpec
    route: Route
    trajectory: Trajectory
    gestures: tuple[Gesture, ...]
    readings: Readings

    @property
    def depart_utc(self) -> datetime:
        """Departure as a whole UTC second: GNSS epochs fall on whole seconds of ride time."""
        return self.spec.depart.astimezone(UTC).replace(microsecond=0)

    def utc(self, t: float) -> datetime:
        return self.depart_utc + timedelta(seconds=t)


def simulate(city: City, spec: RideSpec) -> SimulatedRide:
    def stream(name: str) -> random.Random:
        return random.Random(f"umi-sim/{spec.seed}/{name}")

    depart_local = spec.depart.astimezone(LOCAL_TZ).replace(microsecond=0)
    route = city.network.route(spec.waypoints, goal=spec.goal, hour=depart_local.hour)
    trajectory = ride(
        route, spec.vehicle, stream("rider"), hour=depart_local.hour, hotspots=city.world.hotspots, pace=spec.pace
    )
    gestures = tuple(plan_gestures(route, trajectory, city.world, spec.habits, stream("button")))
    readings = measure(
        route,
        trajectory,
        gestures,
        city.world,
        vehicle=spec.vehicle,
        depart_local=depart_local,
        weather=Weather.on(depart_local.date()),
        battery_pct=spec.battery_pct,
        lang=spec.habits.lang,
        rng=stream("sensors"),
    )
    return SimulatedRide(spec, route, trajectory, gestures, readings)
