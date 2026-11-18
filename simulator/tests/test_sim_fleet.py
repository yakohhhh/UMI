from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import httpx
import respx
from umi_protocol import Flag, Header, Session, verify_flag
from umi_sim.clip import KeyStore
from umi_sim.fleet import PlannedRide, RiderProfile, plan, rider_ids, run_fleet
from umi_sim.phone import Phone
from umi_sim.rider import Vehicle
from umi_sim.simulation import LOCAL_TZ, City

MONDAY = date(2026, 11, 16)
API = "http://umi.test"


def _signature(rides: list[PlannedRide]) -> list[tuple[str, object]]:
    return [(r.profile.rider_id, r.spec) for r in rides]


def test_a_rider_is_the_same_person_in_every_run(city: City) -> None:
    assert RiderProfile.for_id("sim-0007", city.network) == RiderProfile.for_id("sim-0007", city.network)
    assert rider_ids(3) == ["sim-0001", "sim-0002", "sim-0003"]
    for rider_id in rider_ids(40):
        profile = RiderProfile.for_id(rider_id, city.network)
        if profile.vehicle is not Vehicle.RUN:
            assert math.dist(profile.home.position, profile.work.position) >= 1500


def test_same_seed_same_plan(city: City) -> None:
    first = plan(city.network, riders=10, days=7, start=MONDAY, seed=7)
    assert _signature(first) == _signature(plan(city.network, riders=10, days=7, start=MONDAY, seed=7))
    assert _signature(first) != _signature(plan(city.network, riders=10, days=7, start=MONDAY, seed=8))


def test_plan_follows_the_city_rhythm(city: City) -> None:
    rides = plan(city.network, riders=40, days=14, start=MONDAY, seed=7)
    departures = [r.spec.depart for r in rides]
    assert departures == sorted(departures)
    assert {r.profile.rider_id for r in rides} <= set(rider_ids(40))
    commutes = [r for r in rides if r.profile.vehicle is not Vehicle.RUN and r.spec.depart.weekday() < 5]
    hours = [r.spec.depart.astimezone(LOCAL_TZ).hour for r in commutes]
    peaks = sum(6 <= h <= 9 or 16 <= h <= 20 for h in hours)
    assert peaks == len(hours)
    runs = [r for r in rides if r.profile.vehicle is Vehicle.RUN]
    assert runs
    assert all(len(r.spec.waypoints) == 3 and r.spec.waypoints[0] == r.spec.waypoints[2] for r in runs)
    weekend = [r for r in rides if r.spec.depart.weekday() >= 5 and r.profile.vehicle is not Vehicle.RUN]
    assert weekend
    assert all(10 <= r.spec.depart.astimezone(LOCAL_TZ).hour <= 18 for r in weekend)


async def test_fleet_writes_the_clips_files(city: City, tmp_path: Path) -> None:
    rides = plan(city.network, riders=3, days=2, start=MONDAY, seed=7)
    keys = KeyStore(tmp_path / "keys")
    report = await run_fleet(city, rides, keys=keys, out_dir=tmp_path / "out")
    files = sorted((tmp_path / "out").rglob("*.umis"))
    assert report.planned == len(rides) > 0
    assert report.written == report.recorded == len(files) == len(rides) - report.not_started
    for path in files:
        session = Session.from_bytes(path.read_bytes())
        clip = keys.find(session.header.device_id)
        assert path.parent.name == clip.rider_id
        public = clip.private_key.public_key()
        assert all(verify_flag(public, clip.device_id, session.header.session_id, f) for f in session.of_type(Flag))


async def test_fleet_uploads_through_the_phone(city: City, tmp_path: Path) -> None:
    rides = plan(city.network, riders=3, days=2, start=MONDAY, seed=7)
    keys = KeyStore(tmp_path / "keys")

    def register(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        token = f"tok-{body['athlete']['id']}"
        return httpx.Response(
            201, json={"deviceId": body["deviceId"], "athleteId": body["athlete"]["id"], "token": token}
        )

    receipt = {"activityId": "a", "segmentsMatched": 1, "flags": {"accepted": 1, "rejected": 0}, "events": 2}
    with respx.mock(base_url=API) as backend:
        pair = backend.post("/v1/dev/devices").mock(side_effect=register)
        upload = backend.post("/v1/ingest/sessions").respond(201, json=receipt)
        async with httpx.AsyncClient() as client:
            report = await run_fleet(city, rides, keys=keys, phone=Phone(client, API), concurrency=2)

    riders = {r.profile.rider_id for r in rides}
    assert pair.call_count == len(riders)
    assert upload.call_count == report.uploaded == report.recorded - report.too_short
    assert (report.failed, report.written, report.events) == (0, 0, 2 * report.uploaded)
    for call in upload.calls:
        header = Header.from_bytes(call.request.content)
        assert header.trimmed
        assert call.request.headers["Authorization"] == f"Bearer tok-{keys.find(header.device_id).rider_id}"


async def test_failed_uploads_are_reported_not_fatal(city: City, tmp_path: Path) -> None:
    rides = plan(city.network, riders=2, days=1, start=MONDAY, seed=7)
    with respx.mock(base_url=API) as backend:
        backend.post("/v1/dev/devices").respond(201, json={"deviceId": "x", "athleteId": "y", "token": "t"})
        backend.post("/v1/ingest/sessions").respond(422, json={"detail": "simulated sessions are refused"})
        async with httpx.AsyncClient() as client:
            report = await run_fleet(city, rides, keys=KeyStore(tmp_path), phone=Phone(client, API))
    assert report.failed == report.recorded - report.too_short > 0
    assert "simulated sessions are refused" in report.errors[0]
