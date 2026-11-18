from __future__ import annotations

import json
import math
from collections.abc import AsyncIterator, Callable, Iterator

import httpx
import pytest
import respx
from umi_protocol import Flag, RecordType, Session, Trim, verify_flag
from umi_protocol.constants import FORMAT_MEDIA_TYPE, PRIVACY_TRIM_M
from umi_sim.clip import ClipIdentity, Recording, VirtualClip
from umi_sim.phone import Athlete, BackendError, Pairing, Phone, RequestRejectedError
from umi_sim.places import find_place
from umi_sim.simulation import City, RideSpec, simulate

API = "http://umi.test"
PAIRING = Pairing(device_id="5eed000000000001", athlete_id="sim-0001", token="tok-sim-0001")
RECEIPT = {"activityId": "act-1", "segmentsMatched": 12, "flags": {"accepted": 2, "rejected": 0}, "events": 3}


@pytest.fixture
def backend() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=API, assert_all_called=False) as router:
        yield router


@pytest.fixture
def delays() -> list[float]:
    return []


@pytest.fixture
async def phone(delays: list[float]) -> AsyncIterator[Phone]:
    async def no_wait(seconds: float) -> None:
        delays.append(seconds)

    async with httpx.AsyncClient() as client:
        yield Phone(client, API + "/", attempts=4, backoff_s=0.5, sleep=no_wait)


async def test_pairing_registers_the_simulated_clip(
    backend: respx.MockRouter, phone: Phone, identity: ClipIdentity
) -> None:
    route = backend.post("/v1/dev/devices").respond(
        201, json={"deviceId": identity.device_hex, "athleteId": "sim-0001", "token": "tok"}
    )
    pairing = await phone.pair(identity, Athlete.for_rider("sim-0001", "e-bike"))
    assert pairing == Pairing(identity.device_hex, "sim-0001", "tok")
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "deviceId": "5eed000000000001",
        "serial": "UMI-SIM-0001",
        "publicKeyPem": identity.public_key_pem,
        "hwRev": 0,
        "firmware": "0.1.0",
        "simulated": True,
        "athlete": {"id": "sim-0001", "name": "Sim Rider 1", "vehicle": "e-bike"},
    }


async def test_pairing_again_is_fine(backend: respx.MockRouter, phone: Phone, identity: ClipIdentity) -> None:
    backend.post("/v1/dev/devices").respond(
        200, json={"deviceId": identity.device_hex, "athleteId": "sim-0001", "token": "tok"}
    )
    assert (await phone.pair(identity, Athlete.for_rider("sim-0001", "e-bike"))).token == "tok"


async def test_a_refused_pairing_is_final(
    backend: respx.MockRouter, phone: Phone, identity: ClipIdentity, delays: list[float]
) -> None:
    route = backend.post("/v1/dev/devices").respond(404, json={"detail": "dev endpoints are off in production"})
    with pytest.raises(RequestRejectedError, match="dev endpoints are off") as caught:
        await phone.pair(identity, Athlete.for_rider("sim-0001", "e-bike"))
    assert caught.value.status == 404
    assert route.call_count == 1
    assert not delays


async def test_upload_carries_the_trimmed_session(
    backend: respx.MockRouter, phone: Phone, recording: Recording, identity: ClipIdentity
) -> None:
    route = backend.post("/v1/ingest/sessions").respond(201, json=RECEIPT)
    result = await phone.sync(PAIRING, recording.data)

    assert result.receipt is not None
    assert not result.receipt.duplicate
    assert (result.receipt.activity_id, result.receipt.flags_accepted, result.receipt.events) == ("act-1", 2, 3)
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer tok-sim-0001"
    assert request.headers["Content-Type"] == FORMAT_MEDIA_TYPE
    assert request.content == result.trim.data

    uploaded = Session.from_bytes(request.content)
    assert uploaded.header.trimmed
    assert uploaded.header.simulated
    assert uploaded.records[0] == Trim(0, result.trim.start_m, result.trim.end_m)
    assert result.trim.start_m >= PRIVACY_TRIM_M
    assert result.trim.end_m >= PRIVACY_TRIM_M
    assert result.trim.dropped[RecordType.SAMPLE] > 0
    public = identity.private_key.public_key()
    assert all(verify_flag(public, identity.device_id, uploaded.header.session_id, f) for f in uploaded.of_type(Flag))


async def test_a_session_already_uploaded_is_a_duplicate(
    backend: respx.MockRouter, phone: Phone, recording: Recording
) -> None:
    backend.post("/v1/ingest/sessions").respond(200, json=RECEIPT)
    result = await phone.sync(PAIRING, recording.data)
    assert result.receipt is not None
    assert result.receipt.duplicate


async def test_server_errors_are_retried_with_backoff(
    backend: respx.MockRouter, phone: Phone, recording: Recording, delays: list[float]
) -> None:
    route = backend.post("/v1/ingest/sessions")
    route.side_effect = [httpx.Response(503), httpx.Response(502), httpx.Response(201, json=RECEIPT)]
    result = await phone.sync(PAIRING, recording.data)
    assert result.receipt is not None
    assert route.call_count == 3
    assert delays == [0.5, 1.0]


async def test_network_errors_are_retried(
    backend: respx.MockRouter, phone: Phone, recording: Recording, delays: list[float]
) -> None:
    route = backend.post("/v1/ingest/sessions")
    route.side_effect = [httpx.ConnectError("refused"), httpx.Response(201, json=RECEIPT)]
    assert (await phone.sync(PAIRING, recording.data)).receipt is not None
    assert route.call_count == 2
    assert delays == [0.5]


async def test_retries_give_up_after_the_last_attempt(
    backend: respx.MockRouter, phone: Phone, recording: Recording, delays: list[float]
) -> None:
    route = backend.post("/v1/ingest/sessions").respond(500, json={"detail": "database is down"})
    with pytest.raises(BackendError, match="database is down") as caught:
        await phone.sync(PAIRING, recording.data)
    assert caught.value.status == 500
    assert route.call_count == 4
    assert delays == [0.5, 1.0, 2.0]


@pytest.mark.parametrize("status", [401, 403, 413, 422])
async def test_client_errors_are_final(
    backend: respx.MockRouter, phone: Phone, recording: Recording, delays: list[float], status: int
) -> None:
    route = backend.post("/v1/ingest/sessions").respond(status, json={"detail": "not a trimmed v1 log"})
    with pytest.raises(RequestRejectedError, match="not a trimmed v1 log"):
        await phone.sync(PAIRING, recording.data)
    assert route.call_count == 1
    assert not delays


async def test_a_short_trip_never_leaves_the_phone(
    backend: respx.MockRouter,
    phone: Phone,
    city: City,
    make_spec: Callable[..., RideSpec],
    identity: ClipIdentity,
) -> None:
    route = backend.post("/v1/ingest/sessions").respond(201, json=RECEIPT)
    origin = find_place("Verdaguer").position
    nearby = next(n for n in city.network.nodes if 250 < math.dist(n, origin) < 350)
    spec = make_spec()
    short = RideSpec((origin, nearby), spec.depart, spec.vehicle, spec.seed)
    result = await phone.sync(PAIRING, VirtualClip(identity).record(simulate(city, short)).data)
    assert result.receipt is None
    assert result.trim.reason is not None
    assert "minimum" in result.trim.reason
    assert not route.called


async def test_a_malformed_answer_is_an_error(backend: respx.MockRouter, phone: Phone, recording: Recording) -> None:
    backend.post("/v1/ingest/sessions").respond(201, json={"activityId": "act-1"})
    with pytest.raises(BackendError, match="unexpected upload answer"):
        await phone.sync(PAIRING, recording.data)
