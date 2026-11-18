"""A fleet of virtual riders living their days: commutes, weekend rides and runs.

Who a rider is (vehicle, home, work, pace, how they use the flag button) is
fixed by their id, so ``sim-0007`` is the same person in every run and every
Clip they pair keeps one rider. The seed decides what happens each day: who
rides, when they leave, what they meet on the way. Same seed, same days, same
rides.

Commuters ride to work on most weekdays around the morning peak and back in
the evening; some take a leisure ride at the weekend. Runners do an out-and-back
from home to the seafront a few times a week, early or after work.
"""

from __future__ import annotations

import asyncio
import dataclasses
import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from umi_protocol import Lang

from .clip import KeyStore, NoSessionError, Recording, VirtualClip
from .geo import XY
from .hazards import FlagHabits
from .network import RouteGoal, StreetNetwork
from .phone import Athlete, BackendError, Pairing, Phone
from .places import PLACES, Place, Role
from .rider import Vehicle
from .sensors import DRAIN_PCT_PER_H
from .simulation import LOCAL_TZ, City, RideSpec, simulate

_VEHICLES = ((Vehicle.E_BIKE, 0.35), (Vehicle.BIKE, 0.3), (Vehicle.SCOOTER, 0.15), (Vehicle.RUN, 0.2))
_LANGS = ((Lang.CA, 0.5), (Lang.ES, 0.35), (Lang.EN, 0.15))
# Voice keywords are opt-in (off by default): a minority turns them on.
_VOICE_P = 0.25
_CALM_ROUTE_P = 0.35
_HOME_RADIUS_M = 500.0
_WORK_RADIUS_M = 350.0
_MIN_COMMUTE_M = 1500.0
_COMMUTE_P = 0.8
_RIDE_HOME_P = 0.95
_WEEKEND_RIDE_P = 0.3
_RUN_P = 0.45
_RECHARGE_BELOW_PCT = 25.0


def rider_ids(count: int) -> list[str]:
    return [f"sim-{i:04d}" for i in range(1, count + 1)]


def _weighted[T](rng: random.Random, options: Sequence[tuple[T, float]]) -> T:
    return rng.choices([o for o, _ in options], weights=[w for _, w in options])[0]


def _minutes(rng: random.Random, mean: float, sd: float, lo: float, hi: float) -> int:
    return round(min(max(rng.gauss(mean, sd), lo), hi))


@dataclass(frozen=True, slots=True)
class Anchor:
    """A rider's home or work: a junction near one of the named places."""

    place: Place
    position: XY


@dataclass(frozen=True, slots=True)
class RiderProfile:
    rider_id: str
    vehicle: Vehicle
    home: Anchor
    work: Anchor
    habits: FlagHabits
    pace: float
    goal: RouteGoal
    leaves_min: int
    returns_min: int

    @property
    def athlete(self) -> Athlete:
        return Athlete.for_rider(self.rider_id, self.vehicle.value)

    @classmethod
    def for_id(cls, rider_id: str, network: StreetNetwork) -> RiderProfile:
        rng = random.Random(f"umi-sim/rider/{rider_id}")
        vehicle = _weighted(rng, _VEHICLES)
        home = _anchor(rng, network, [p for p in PLACES if Role.HOME in p.roles], _HOME_RADIUS_M)
        if vehicle is Vehicle.RUN:
            # A runner's "work" is where they turn back: a spot by the sea.
            work = _anchor(rng, network, [p for p in PLACES if Role.LEISURE in p.roles], _WORK_RADIUS_M)
            leaves = _minutes(rng, 7 * 60 + 15, 30, 6 * 60, 8 * 60 + 30)
            returns = _minutes(rng, 19 * 60 + 45, 30, 18 * 60 + 30, 21 * 60)
        else:
            # Far enough that the commute stays worth riding wherever the anchor lands.
            work_places = [
                p
                for p in PLACES
                if Role.WORK in p.roles and math.dist(p.position, home.position) >= _MIN_COMMUTE_M + _WORK_RADIUS_M
            ]
            work = _anchor(rng, network, work_places, _WORK_RADIUS_M)
            leaves = _minutes(rng, 8 * 60, 25, 6 * 60 + 50, 9 * 60 + 45)
            returns = _minutes(rng, 18 * 60 + 15, 40, 16 * 60 + 30, 20 * 60 + 30)
        habits = FlagHabits(
            propensity=rng.uniform(0.2, 0.85), voice=rng.random() < _VOICE_P, lang=_weighted(rng, _LANGS)
        )
        pace = min(max(rng.gauss(1.0, 0.07), 0.85), 1.15)
        goal = RouteGoal.CALMEST if rng.random() < _CALM_ROUTE_P else RouteGoal.FASTEST
        return cls(rider_id, vehicle, home, work, habits, pace, goal, leaves, returns)


def _anchor(rng: random.Random, network: StreetNetwork, places: Sequence[Place], radius_m: float) -> Anchor:
    place = rng.choice(places)
    nearby = [n for n in network.nodes if math.dist(n, place.position) <= radius_m] or [place.position]
    return Anchor(place, rng.choice(nearby))


@dataclass(frozen=True, slots=True)
class PlannedRide:
    profile: RiderProfile
    spec: RideSpec
    label: str


def plan(network: StreetNetwork, *, riders: int, days: int, start: date, seed: int) -> list[PlannedRide]:
    """Every ride of the fleet over ``days`` days from ``start``, in departure order."""
    profiles = [RiderProfile.for_id(rider_id, network) for rider_id in rider_ids(riders)]
    rides = [
        ride
        for day in (start + timedelta(days=d) for d in range(days))
        for profile in profiles
        for ride in _day(profile, day, seed)
    ]
    return sorted(rides, key=lambda r: (r.spec.depart, r.profile.rider_id))


def _day(profile: RiderProfile, day: date, seed: int) -> list[PlannedRide]:
    rng = random.Random(f"umi-sim/fleet/{seed}/{profile.rider_id}/{day.isoformat()}")
    home, work = profile.home, profile.work

    def ride(origin: Anchor, *via: Anchor, at_min: float) -> PlannedRide:
        depart = datetime.combine(day, time(), LOCAL_TZ) + timedelta(minutes=at_min, seconds=rng.randrange(60))
        spec = RideSpec(
            waypoints=(origin.position, *(a.position for a in via)),
            depart=depart,
            vehicle=profile.vehicle,
            seed=rng.getrandbits(32),
            goal=profile.goal,
            habits=profile.habits,
            pace=profile.pace * rng.gauss(1.0, 0.03),
        )
        return PlannedRide(profile, spec, " → ".join(a.place.name for a in (origin, *via)))

    if profile.vehicle is Vehicle.RUN:
        if rng.random() >= _RUN_P:
            return []
        at = profile.leaves_min if rng.random() < 0.5 else profile.returns_min
        return [ride(home, work, home, at_min=at + rng.gauss(0, 15))]
    if day.weekday() >= 5:
        if rng.random() >= _WEEKEND_RIDE_P:
            return []
        spots = [p for p in PLACES if Role.LEISURE in p.roles and math.dist(p.position, home.position) > _MIN_COMMUTE_M]
        if not spots:
            return []
        spot = rng.choice(spots)
        outing = Anchor(spot, spot.position)
        out_at = rng.uniform(10 * 60 + 30, 12 * 60 + 30)
        back_at = out_at + rng.uniform(90, 300)
        return [ride(home, outing, at_min=out_at), ride(outing, home, at_min=back_at)]
    if rng.random() >= _COMMUTE_P:
        return []
    rides = [ride(home, work, at_min=profile.leaves_min + rng.gauss(0, 8))]
    if rng.random() < _RIDE_HOME_P:
        rides.append(ride(work, home, at_min=profile.returns_min + rng.gauss(0, 15)))
    return rides


@dataclass
class FleetReport:
    planned: int = 0
    recorded: int = 0
    written: int = 0
    uploaded: int = 0
    duplicates: int = 0
    too_short: int = 0
    not_started: int = 0
    failed: int = 0
    flags_accepted: int = 0
    flags_rejected: int = 0
    events: int = 0
    errors: list[str] = field(default_factory=list)


type Progress = Callable[[PlannedRide, Recording], None]


async def run_fleet(
    city: City,
    rides: Sequence[PlannedRide],
    *,
    keys: KeyStore,
    out_dir: Path | None = None,
    phone: Phone | None = None,
    concurrency: int = 8,
    progress: Progress | None = None,
) -> FleetReport:
    """Record every planned ride; write the Clip's files and/or let the phone trim and upload them.

    Rides are simulated one after the other, in departure order, so each Clip's
    battery carries over from ride to ride. Uploads run concurrently (at most
    ``concurrency`` at a time) while the next rides are simulated.
    """
    report = FleetReport(planned=len(rides))
    battery: dict[str, float] = {}
    pairings: dict[str, Pairing] = {}
    slots = asyncio.Semaphore(concurrency)

    def failed(planned: PlannedRide, exc: BackendError) -> None:
        report.failed += 1
        report.errors.append(f"{planned.profile.rider_id} {planned.label}: {exc}")

    async def upload(phone: Phone, pairing: Pairing, planned: PlannedRide, recording: Recording) -> None:
        try:
            result = await phone.sync(pairing, recording.data)
        except BackendError as exc:
            failed(planned, exc)
            return
        finally:
            slots.release()
        if result.receipt is None:
            report.too_short += 1
            return
        report.uploaded += 1
        report.duplicates += result.receipt.duplicate
        report.flags_accepted += result.receipt.flags_accepted
        report.flags_rejected += result.receipt.flags_rejected
        report.events += result.receipt.events

    async with asyncio.TaskGroup() as uploads:
        for planned in rides:
            rider = planned.profile.rider_id
            charge = battery.get(rider, 100.0)
            if charge < _RECHARGE_BELOW_PCT:
                charge = 100.0  # charged overnight
            spec = dataclasses.replace(planned.spec, battery_pct=charge)
            clip = VirtualClip(keys.clip_for(rider))
            try:
                recording, awake_s = await asyncio.to_thread(_record, city, spec, clip)
            except NoSessionError:
                report.not_started += 1
                continue
            battery[rider] = charge - DRAIN_PCT_PER_H * awake_s / 3600
            report.recorded += 1
            if progress is not None:
                progress(planned, recording)
            if out_dir is not None:
                _write(out_dir, rider, recording)
                report.written += 1
            if phone is not None:
                try:
                    if rider not in pairings:
                        pairings[rider] = await phone.pair(clip.identity, planned.profile.athlete)
                except BackendError as exc:
                    failed(planned, exc)
                    continue
                await slots.acquire()
                uploads.create_task(upload(phone, pairings[rider], planned, recording))
    return report


def _record(city: City, spec: RideSpec, clip: VirtualClip) -> tuple[Recording, float]:
    ride = simulate(city, spec)
    return clip.record(ride), ride.readings.end - ride.readings.t0


def _write(out_dir: Path, rider_id: str, recording: Recording) -> Path:
    folder = out_dir / rider_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{recording.started_at.astimezone(LOCAL_TZ):%Y%m%d-%H%M}-{recording.session_id}.umis"
    path.write_bytes(recording.data)
    return path
