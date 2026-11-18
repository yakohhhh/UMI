"""Shared fixtures: the city, a Clip with a fixed key, and one commute recorded once per session."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from umi_protocol import Lang
from umi_sim.clip import ClipIdentity, Recording, VirtualClip
from umi_sim.hazards import FlagHabits
from umi_sim.places import find_place
from umi_sim.rider import Vehicle
from umi_sim.simulation import LOCAL_TZ, City, RideSpec, SimulatedRide, simulate

DEPART = datetime(2026, 11, 18, 7, 50, tzinfo=LOCAL_TZ)
# A rider who flags everything and talks to the Clip, so one ride exercises every gesture.
EAGER = FlagHabits(propensity=1.0, voice=True, lang=Lang.CA)


@pytest.fixture(scope="session")
def city() -> City:
    return City.load()


@pytest.fixture(scope="session")
def identity() -> ClipIdentity:
    return ClipIdentity(
        rider_id="sim-0001",
        device_id=0x5EED_0000_0000_0001,
        serial="UMI-SIM-0001",
        private_key=ec.derive_private_key(0x1D_C0FF_EE, ec.SECP256R1()),
    )


@pytest.fixture(scope="session")
def make_spec() -> Callable[..., RideSpec]:
    def make(
        origin: str = "Gràcia",
        destination: str = "22@",
        *,
        seed: int = 2,
        vehicle: Vehicle = Vehicle.E_BIKE,
        habits: FlagHabits = EAGER,
        depart: datetime = DEPART,
    ) -> RideSpec:
        waypoints = (find_place(origin).position, find_place(destination).position)
        return RideSpec(waypoints, depart, vehicle, seed, habits=habits)

    return make


@pytest.fixture(scope="session")
def commute(city: City, make_spec: Callable[..., RideSpec]) -> SimulatedRide:
    return simulate(city, make_spec())


@pytest.fixture(scope="session")
def recording(commute: SimulatedRide, identity: ClipIdentity) -> Recording:
    return VirtualClip(identity).record(commute)
