from __future__ import annotations

import random
from itertools import pairwise

import pytest
from umi_protocol.constants import DETECTION_HARD_BRAKE_MPS2
from umi_sim.network import Route
from umi_sim.places import find_place
from umi_sim.rider import DYNAMICS, KMH, Trajectory, Vehicle, ride
from umi_sim.simulation import City


@pytest.fixture(scope="module")
def route(city: City) -> Route:
    return city.network.route([find_place("Gràcia").position, find_place("22@").position], hour=8)


def _ride(city: City, route: Route, vehicle: Vehicle = Vehicle.E_BIKE, seed: int = 1) -> Trajectory:
    return ride(route, vehicle, random.Random(seed), hour=8, hotspots=city.world.hotspots)


def test_same_seed_same_ride(city: City, route: Route) -> None:
    assert _ride(city, route, seed=3).knots == _ride(city, route, seed=3).knots
    assert _ride(city, route, seed=3).knots != _ride(city, route, seed=4).knots


@pytest.mark.parametrize("vehicle", list(Vehicle))
def test_profile_respects_the_riders_limits(city: City, route: Route, vehicle: Vehicle) -> None:
    dyn = DYNAMICS[vehicle]
    trajectory = _ride(city, route, vehicle)
    knots = trajectory.knots
    assert knots[0].v == knots[-1].v == 0.0
    assert trajectory.length == pytest.approx(route.length)
    for k0, k1 in pairwise(knots):
        assert k1.t >= k0.t
        assert k1.s >= k0.s
        assert 0.0 <= k1.v <= dyn.max_kmh * KMH + 1e-9
        if k1.t > k0.t:
            a = (k1.v - k0.v) / (k1.t - k0.t)
            assert a <= dyn.accel + 1e-6
            assert -a <= max(dyn.decel, dyn.hard_brake[1]) + 1e-6
    average_kmh = route.length / trajectory.arrival * 3.6
    assert 0.5 * dyn.cruise_kmh < average_kmh < dyn.cruise_kmh


def test_position_and_time_agree(city: City, route: Route) -> None:
    trajectory = _ride(city, route)
    for t in (12.0, 100.5, 333.3, trajectory.arrival - 5):
        state = trajectory.state_at(t)
        if state.v > 0.5:
            assert trajectory.time_at(state.s) == pytest.approx(t, abs=1e-6)
    assert trajectory.state_at(-3.0).s == 0.0
    assert trajectory.state_at(trajectory.arrival + 60).s == pytest.approx(route.length)


def test_red_lights_stop_the_rider(city: City, route: Route) -> None:
    stops = [(k0, k1) for k0, k1 in pairwise(_ride(city, route).knots) if k0.s == k1.s and k1.t > k0.t]
    assert stops
    assert all(k0.v == k1.v == 0.0 for k0, k1 in stops)


def test_hard_brakes_are_hard_and_runners_have_none(city: City, route: Route) -> None:
    brakes = [b for seed in range(10) for b in _ride(city, route, seed=seed).decelerations(DETECTION_HARD_BRAKE_MPS2)]
    assert brakes
    lo, hi = DYNAMICS[Vehicle.E_BIKE].hard_brake
    assert all(lo - 1e-6 <= b.mean <= hi + 1e-6 for b in brakes)
    assert not _ride(city, route, Vehicle.RUN).decelerations(DETECTION_HARD_BRAKE_MPS2)


def test_hotspots_make_hard_brakes_more_likely(city: City, route: Route) -> None:
    def count(hotspots: bool) -> int:
        world = city.world.hotspots if hotspots else ()
        return sum(
            len(ride(route, Vehicle.E_BIKE, random.Random(seed), hour=8, hotspots=world).decelerations(3.0))
            for seed in range(30)
        )

    assert count(hotspots=True) > count(hotspots=False)
