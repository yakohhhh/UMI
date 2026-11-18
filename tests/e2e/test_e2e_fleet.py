"""The simulator's riders against the backend: pairing, privacy trim, upload, feeds and shared hazards.

The fast, in-process version of running ``umi-sim fleet --api`` against
``umi-api serve`` (README.md, "Live run"): the simulator's phone talks to the
ASGI app, so the whole path from a virtual Clip's bytes to the read endpoints
runs in a few seconds without a server or a network.
"""

import dataclasses
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from umi_protocol import Session, trim_session
from umi_protocol.constants import FORMAT_MEDIA_TYPE, PRIVACY_CITY_MIN_RIDERS, PRIVACY_MAP_MIN_RIDERS
from umi_sim.clip import KeyStore, Recording, VirtualClip
from umi_sim.fleet import PlannedRide, plan, run_fleet
from umi_sim.hazards import Gesture, GestureKind
from umi_sim.phone import Athlete, Pairing, Phone
from umi_sim.places import find_place
from umi_sim.rider import Vehicle
from umi_sim.simulation import LOCAL_TZ, City, RideSpec, SimulatedRide, simulate

from .demo import DEMO_NOW

pytestmark = pytest.mark.e2e

MORNING = DEMO_NOW.astimezone(LOCAL_TZ).replace(hour=7, minute=40, second=0, microsecond=0)


def _auth(rider_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer dev:{rider_id}"}


async def _get(api: httpx.AsyncClient, path: str, rider_id: str) -> Any:
    response = await api.get(path, headers=_auth(rider_id))
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_fleet_uploads_once_and_each_rider_sees_their_rides(
    city: City, keys: KeyStore, phone: Phone, api: httpx.AsyncClient
) -> None:
    # Two weekdays that end before the API's "now", which uploads may not come after.
    days = 2
    rides = plan(city.network, riders=4, days=days, start=DEMO_NOW.date() - timedelta(days=days), seed=7)
    recorded: list[tuple[PlannedRide, Recording]] = []

    report = await run_fleet(city, rides, keys=keys, phone=phone, progress=lambda p, r: recorded.append((p, r)))

    assert report.failed == 0, report.errors
    assert report.recorded == len(recorded) > 0
    assert report.uploaded == report.recorded - report.too_short > 0
    assert (report.duplicates, report.flags_rejected) == (0, 0)

    again = await run_fleet(city, rides, keys=keys, phone=phone)
    assert (again.uploaded, again.duplicates, again.failed) == (report.uploaded, report.uploaded, 0)

    for rider_id in {p.profile.rider_id for p, _ in recorded}:
        uploaded = [r for p, r in recorded if p.profile.rider_id == rider_id and trim_session(r.data).data]
        feed = await _get(api, "/v1/feed", rider_id)
        own = sorted(a["startedAt"] for a in feed if a["athleteId"] == rider_id)
        assert len(own) == len(uploaded), rider_id


async def test_an_untrimmed_session_is_refused_and_not_stored(
    city: City, keys: KeyStore, phone: Phone, api: httpx.AsyncClient
) -> None:
    clip = keys.clip_for("sim-0001")
    pairing = await phone.pair(clip, Athlete.for_rider(clip.rider_id, "e-bike"))
    spec = RideSpec((find_place("Gràcia").position, find_place("22@").position), MORNING, Vehicle.E_BIKE, seed=3)
    recording = VirtualClip(clip).record(simulate(city, spec))
    assert not Session.from_bytes(recording.data).header.trimmed

    response = await api.post(
        "/v1/ingest/sessions",
        content=recording.data,
        headers={"Authorization": f"Bearer {pairing.token}", "Content-Type": FORMAT_MEDIA_TYPE},
    )

    assert response.status_code == 422
    assert "not trimmed" in response.json()["detail"]
    assert not [a for a in await _get(api, "/v1/feed", clip.rider_id) if a["athleteId"] == clip.rider_id]


def _pressing_at(city: City, spec: RideSpec, fraction: float) -> SimulatedRide:
    """The ride, with one press a second after the rider passes ``fraction`` of the route and no other gesture.

    Readings depend on gestures only through what the keyword recogniser heard
    during a hold, so a press-only ride keeps every other reading as simulated.
    """
    ride = simulate(city, spec)
    t = ride.trajectory.time_at(ride.route.length * fraction) + 1.0
    return dataclasses.replace(ride, gestures=(Gesture(GestureKind.PRESS, t),))


async def _status(api: httpx.AsyncClient, rider_id: str, activity_id: str) -> tuple[str, int]:
    flag = (await _get(api, f"/v1/activities/{activity_id}", rider_id))["flags"][0]
    return flag["status"], flag["confirmations"]


async def _published(api: httpx.AsyncClient, path: str, hazard_id: str) -> list[int]:
    hazards: list[dict[str, Any]] = (await api.get(path)).json()
    return [h["riders"] for h in hazards if h["id"] == hazard_id]


async def test_distinct_riders_flagging_one_corner_move_its_hazard_to_the_map_then_the_city(
    city: City, keys: KeyStore, phone: Phone, api: httpx.AsyncClient
) -> None:
    riders = [keys.clip_for(f"sim-{n:04d}") for n in range(1, PRIVACY_CITY_MIN_RIDERS + 1)]
    first_activity = hazard_id = ""
    for n, clip in enumerate(riders, start=1):
        pairing: Pairing = await phone.pair(clip, Athlete.for_rider(clip.rider_id, "bike"))
        # Same street, their own pace, GNSS error and departure. The seafront has no seeded hazard, so the first
        # flag opens a new one instead of joining a demo hazard within the merge radius.
        depart: datetime = MORNING + timedelta(minutes=6 * n)
        spec = RideSpec((find_place("Bogatell").position, find_place("Fòrum").position), depart, Vehicle.BIKE, seed=n)
        result = await phone.sync(pairing, VirtualClip(clip).record(_pressing_at(city, spec, 0.5)).data)
        assert result.receipt is not None
        assert (result.receipt.flags_accepted, result.receipt.flags_rejected) == (1, 0)

        if n == 1:
            first_activity, hazard_id = result.receipt.activity_id, f"{result.receipt.activity_id}-f0"
            # Pressed without a keyword: the rider says what it was after the ride, which names the hazard.
            answer = await api.post(
                f"/v1/me/activities/{first_activity}/flags/{hazard_id}",
                json={"kind": "pothole"},
                headers=_auth(clip.rider_id),
            )
            assert answer.status_code == 200, answer.text

        status = "pending"
        if n >= PRIVACY_MAP_MIN_RIDERS:
            status = "verified"
        if n >= PRIVACY_CITY_MIN_RIDERS:
            status = "sent_to_city"
        assert await _status(api, riders[0].rider_id, first_activity) == (status, n - 1), f"after {n} riders"
        assert await _published(api, "/v1/hazards", hazard_id) == ([n] if n >= PRIVACY_MAP_MIN_RIDERS else [])
        in_city = await _published(api, "/v1/city/hazards", hazard_id)
        assert in_city == ([n] if n >= PRIVACY_CITY_MIN_RIDERS else [])
