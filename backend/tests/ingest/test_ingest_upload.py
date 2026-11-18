"""POST /v1/ingest/sessions and POST /v1/dev/devices: what is accepted, what is refused, and where a ride shows."""

from collections.abc import Callable
from datetime import datetime, timedelta

import httpx
import pytest
from umi_protocol import HazardKind
from umi_protocol.constants import FORMAT_MEDIA_TYPE

from .riders import SESSIONS, MakeApi, MakeRider, Rider
from .sessions import MALLORCA, Brake, Press, RideSpec, SoftwareClip, Stretch, record


async def test_a_ride_shows_everywhere_its_rider_looks(rider: Rider, ride_start: datetime) -> None:
    spec = RideSpec(
        start=ride_start,
        presses=(Press(700, HazardKind.POTHOLE, confidence=90), Press(1100)),
        brakes=(Brake(900, 5.0),),
        smoky=(Stretch(400, 500),),
        loud=(Stretch(1200, 1300),),
    )
    receipt = await rider.ride(spec)

    activity_id = "ona-20261112-0830"  # the rider and the local start minute
    assert receipt == {
        "activityId": activity_id,
        "segmentsMatched": 4,
        "flags": {"accepted": 2, "rejected": 0},
        "events": 3,
    }
    feed = await rider.get("/v1/feed")
    assert [a["id"] for a in feed] == [activity_id]
    ride = await rider.get(f"/v1/activities/{activity_id}")
    assert ride["type"] == "ride"
    assert ride["title"] == "Morning ride"
    assert ride["place"] == "Eixample"
    # The trimmed ends count in the distance, never in the trace.
    assert 1850 <= ride["distanceM"] <= 1890
    assert ride["avgSpeedKmh"] == 18.0
    assert [s["segmentId"] for s in ride["segments"]] == list(MALLORCA)
    assert all(isinstance(s["streetAverage"], int) for s in ride["segments"])
    assert [e["type"] for e in ride["events"]] == ["pm_spike", "hard_brake", "noise_peak"]
    assert [(f["kind"], f["source"], f["status"]) for f in ride["flags"]] == [
        ("pothole", "voice", "pending"),
        (None, "press", "pending"),
    ]

    samples = ride["samples"]
    assert all(len(s) == 7 for s in samples)
    t, distance, speed, _vib, pm25, _db, route_index = zip(*samples, strict=True)
    assert list(t) == sorted(t)
    assert distance[0] >= 200, "the first 200 m stay on the phone"
    assert set(speed) == {18.0}
    # PM2.5 holds the last AIR reading (every 10 s) between readings.
    assert set(pm25) == {12.0, 40.0}
    assert all(0 <= i < len(ride["route"]) for i in route_index)

    profile = await rider.get("/v1/me/profile")
    assert {f["id"] for f in profile["contributions"]["flags"]} == {f["id"] for f in ride["flags"]}
    clip = await rider.get("/v1/me/clip")
    assert (clip["serial"], clip["firmware"], clip["battery"]) == ("UMI-TEST-0001", "0.9.0", 80)
    exposure = await rider.get("/v1/me/exposure", range="7d")
    assert [(d["date"], d["rideMin"]) for d in exposure["days"]] == [(ride_start.date().isoformat(), 6)]


async def test_another_rider_does_not_see_the_ride(rider: Rider, api: httpx.AsyncClient, ride_start: datetime) -> None:
    receipt = await rider.ride(RideSpec(start=ride_start))
    response = await api.get(f"/v1/activities/{receipt['activityId']}", headers={"Authorization": "Bearer dev:laia"})
    assert response.status_code == 404


async def test_uploading_again_returns_the_first_receipt(rider: Rider, ride_start: datetime) -> None:
    body = rider.session(RideSpec(start=ride_start, presses=(Press(800),)))
    first = await rider.upload(body)
    again = await rider.upload(body)

    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json()
    assert len(await rider.get("/v1/feed")) == 1
    assert len((await rider.get("/v1/me/profile"))["contributions"]["flags"]) == 1


async def test_two_rides_starting_the_same_minute_get_distinct_ids(make_rider: MakeRider, ride_start: datetime) -> None:
    # The same rider with two Clips (the second one paired later).
    first_clip, second_clip = await make_rider("ona", 1), await make_rider("ona", 2)
    first = await first_clip.ride(RideSpec(start=ride_start))
    second = await second_clip.ride(RideSpec(start=ride_start))
    assert (first["activityId"], second["activityId"]) == ("ona-20261112-0830", "ona-20261112-0830-2")


@pytest.mark.parametrize(
    ("spec_changes", "trim", "reason"),
    [
        ({}, False, "not trimmed"),
        ({"time_sync": False}, True, "TIME_SYNC"),
    ],
)
async def test_sessions_the_protocol_refuses(
    rider: Rider, ride_start: datetime, spec_changes: dict[str, bool], trim: bool, reason: str
) -> None:
    spec = RideSpec(start=ride_start, **spec_changes)
    body = rider.session(spec) if trim else record(spec, rider.clip, 1)
    response = await rider.upload(body)
    assert response.status_code == 422
    assert reason in response.json()["detail"]


async def test_bytes_that_are_not_a_session_log(rider: Rider) -> None:
    response = await rider.upload(b"UMIS" + bytes(60))
    assert response.status_code == 422
    assert "Not a valid UMI v1 session log" in response.json()["detail"]


async def test_simulated_sessions_are_refused_when_disabled(
    make_api: MakeApi, make_rider: MakeRider, api: httpx.AsyncClient, ride_start: datetime
) -> None:
    real_clip = SoftwareClip.numbered(2)
    assert (await api.post("/v1/dev/devices", json=real_clip.registration("pau", simulated=False))).is_success
    async with await make_api(accept_simulated=False) as strict:
        sim = await make_rider("ona", 1, client=strict)
        real = Rider("pau", real_clip, strict)
        simulated = await sim.upload(sim.session(RideSpec(start=ride_start)))
        # A Clip registered as simulated is refused even when its header says otherwise.
        unflagged = await sim.upload(sim.session(RideSpec(start=ride_start, simulated=False)))
        accepted = await real.upload(real.session(RideSpec(start=ride_start, simulated=False)))

    assert (simulated.status_code, unflagged.status_code, accepted.status_code) == (422, 422, 201)
    assert "simulated" in simulated.json()["detail"]


async def test_a_clip_paired_with_someone_else_is_forbidden(make_rider: MakeRider, ride_start: datetime) -> None:
    ona = await make_rider("ona", 1)
    pau = await make_rider("pau", 2)
    response = await pau.upload(ona.session(RideSpec(start=ride_start)))
    assert response.status_code == 403


async def test_an_unknown_clip_is_forbidden(api: httpx.AsyncClient, ride_start: datetime) -> None:
    unknown = Rider("laia", SoftwareClip.numbered(9), api)
    response = await unknown.upload(unknown.session(RideSpec(start=ride_start)))
    assert response.status_code == 403


async def test_an_unknown_rider_is_unauthorized(api: httpx.AsyncClient, rider: Rider, ride_start: datetime) -> None:
    headers = {"Authorization": "Bearer dev:nobody", "Content-Type": FORMAT_MEDIA_TYPE}
    response = await api.post(SESSIONS, content=rider.session(RideSpec(start=ride_start)), headers=headers)
    assert response.status_code == 401


async def test_the_body_must_be_a_session_log_under_2_mib(rider: Rider, api: httpx.AsyncClient) -> None:
    as_json = await api.post(SESSIONS, json={"session": "..."}, headers=rider.auth)
    too_large = await rider.upload(bytes(2 * 1024 * 1024 + 1))
    assert (as_json.status_code, too_large.status_code) == (415, 413)


@pytest.mark.parametrize(
    ("spec", "reason"),
    [
        (lambda start: RideSpec(start=start, speed_kmh=75.0), "faster than 60 km/h"),
        (lambda start: RideSpec(start=start, shift_deg=(0.5, 0.0)), "service area"),
        (lambda start: RideSpec(start=start + timedelta(days=1)), "in the future"),
        (lambda start: RideSpec(start=start - timedelta(days=400)), "more than a year old"),
    ],
    ids=["by car", "outside Barcelona", "in the future", "a year old"],
)
async def test_implausible_sessions_are_refused(
    rider: Rider, ride_start: datetime, spec: Callable[[datetime], RideSpec], reason: str
) -> None:
    response = await rider.upload(rider.session(spec(ride_start)))
    assert response.status_code == 422
    assert reason in response.json()["detail"]


class TestDevDevices:
    async def test_registering_creates_the_rider_and_pairs_the_clip(self, api: httpx.AsyncClient) -> None:
        clip = SoftwareClip.numbered(1)
        first = await api.post("/v1/dev/devices", json=clip.registration("ona"))
        again = await api.post("/v1/dev/devices", json=clip.registration("ona"))

        assert first.status_code == 201
        assert first.json() == {"deviceId": clip.device_hex, "athleteId": "ona", "token": "dev:ona"}
        assert (again.status_code, again.json()) == (200, first.json())
        me = (await api.get("/v1/me", headers={"Authorization": "Bearer dev:ona"})).json()
        assert (me["name"], me["firstName"], me["initials"], me["vehicle"]) == ("Test Ona", "Test", "TO", "e-bike")

    async def test_another_key_for_the_same_clip_is_a_conflict(self, api: httpx.AsyncClient) -> None:
        clip = SoftwareClip.numbered(1)
        assert (await api.post("/v1/dev/devices", json=clip.registration("ona"))).status_code == 201
        impostor = {
            **clip.registration("ona"),
            "publicKeyPem": SoftwareClip.numbered(2).registration("x")["publicKeyPem"],
        }
        assert (await api.post("/v1/dev/devices", json=impostor)).status_code == 409

    async def test_a_serial_belongs_to_one_clip(self, api: httpx.AsyncClient) -> None:
        assert (await api.post("/v1/dev/devices", json=SoftwareClip.numbered(1).registration("ona"))).status_code == 201
        other = {**SoftwareClip.numbered(2).registration("pau"), "serial": "UMI-TEST-0001"}
        assert (await api.post("/v1/dev/devices", json=other)).status_code == 409

    async def test_the_key_must_be_a_p256_public_key(self, api: httpx.AsyncClient) -> None:
        body = {**SoftwareClip.numbered(1).registration("ona"), "publicKeyPem": "-----BEGIN PUBLIC KEY-----\nAAAA\n"}
        response = await api.post("/v1/dev/devices", json=body)
        assert response.status_code == 422
        assert "publicKeyPem" in response.json()["detail"]

    async def test_not_in_production(self, make_api: MakeApi) -> None:
        async with await make_api(env="production") as production:
            response = await production.post("/v1/dev/devices", json=SoftwareClip.numbered(1).registration("ona"))
        assert response.status_code == 404
