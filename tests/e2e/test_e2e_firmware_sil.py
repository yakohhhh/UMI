"""A simulated ride through the real firmware, the phone and the backend, checked against what the rider did.

``umi-sim`` exports the ride's raw sensor streams as a SIL scenario; the firmware's
SIL program (``pio run -e sil``) runs the Clip's own code on them and writes the
``.umis``; the reference codec decodes it and verifies every flag signature; the
phone trims it and uploads it to the backend, and the ride shows in the rider's
feed. The Clip's records are checked against the simulation's ground truth: an
EVENT where the rider braked hard or hit a pothole and nowhere else, a FLAG for
every press and hold (with the keyword the recogniser understood), a FLAG_UNDO for
every double press.
"""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from umi_protocol import (
    Event,
    EventKind,
    Flag,
    FlagSource,
    FlagUndo,
    HazardKind,
    Lang,
    Session,
    SigAlg,
    effective_flags,
    private_key_to_raw_hex,
    verify_flag,
)
from umi_protocol.constants import (
    BUTTON_DEBOUNCE_MS,
    BUTTON_DOUBLE_PRESS_GAP_MS,
    BUTTON_KEYWORD_MIN_CONFIDENCE,
    DETECTION_HARD_BRAKE_MIN_MS,
    DETECTION_HARD_BRAKE_MPS2,
    DETECTION_HARD_BRAKE_REFRACTORY_MS,
    DETECTION_POTHOLE_PEAK_MPS2,
    DETECTION_POTHOLE_REFRACTORY_MS,
    DETECTION_POTHOLE_RMS_MPS2,
    PRIVACY_TRIM_M,
)
from umi_sim.clip import ClipIdentity
from umi_sim.hazards import FlagHabits, GestureKind
from umi_sim.phone import Athlete, Phone
from umi_sim.places import find_place
from umi_sim.rider import Vehicle
from umi_sim.scenario import write_scenario
from umi_sim.simulation import LOCAL_TZ, City, RideSpec, SimulatedRide, simulate

from .demo import DEMO_NOW

pytestmark = pytest.mark.e2e

CLIP = ClipIdentity(
    rider_id="sim-e2e-0001",
    device_id=0x5EED_E2E0_0000_0001,
    serial="UMI-SIM-E2E-0001",
    # TEST ONLY: a fixed key keeps the run reproducible byte for byte.
    private_key=ec.derive_private_key(0xE2E_5_11, ec.SECP256R1()),
)
SESSION_ID = 1
# Gràcia → 22@ on an e-bike the morning of the demo's "now", seed 1: a hold the
# recogniser did not understand, a hold it did (pothole), a press undone with a
# double press, a hold undone the same way, and hard brakes and potholes on the way.
SPEC = RideSpec(
    waypoints=(find_place("Gràcia").position, find_place("22@").position),
    depart=DEMO_NOW.astimezone(LOCAL_TZ).replace(hour=7, minute=50, second=0, microsecond=0),
    vehicle=Vehicle.E_BIKE,
    seed=1,
    habits=FlagHabits(propensity=1.0, voice=True, lang=Lang.CA),
)
# Detection runs on the 100 Hz IMU while the ground truth is continuous: an event
# is "where the rider braked" within this much, and only clear cases must fire.
_ONSET_TOLERANCE_MS = 600
_CLEARLY_ABOVE = 1.1


@dataclass(frozen=True)
class SilRun:
    ride: SimulatedRide
    data: bytes
    session: Session

    def at_ms(self, t: float) -> int:
        """Unix milliseconds of ride time ``t`` (ground truth)."""
        return round(self.ride.utc(t).timestamp() * 1000)

    def unix_ms(self, t_ms: int) -> int:
        """Unix milliseconds of a record's session time."""
        unix_ms = self.session.unix_ms(t_ms)
        assert unix_ms is not None, "the session has no TIME_SYNC"
        return unix_ms

    def in_session(self, t: float) -> bool:
        return self.unix_ms(0) <= self.at_ms(t) <= self.unix_ms(self.session.duration_ms)

    def events(self, kind: EventKind) -> list[int]:
        """Unix milliseconds of the onsets of the Clip's events of a kind."""
        return [self.unix_ms(e.t_ms) for e in self.session.of_type(Event) if e.kind == kind]


@pytest.fixture(scope="module")
def sil_run(sil_program: Path, city: City, tmp_path_factory: pytest.TempPathFactory) -> SilRun:
    ride = simulate(city, SPEC)
    folder = tmp_path_factory.mktemp("sil")
    scenario, out = folder / "ride.scn", folder / "ride.umis"
    with scenario.open("w", encoding="utf-8", newline="\n") as file:
        write_scenario(ride, file, title="e2e: Gràcia → 22@, e-bike, seed 1")
    command = [
        str(sil_program),
        *("--scenario", str(scenario), "--out", str(out)),
        *("--device-id", CLIP.device_hex, "--session-id", str(SESSION_ID)),
        *("--key-hex", private_key_to_raw_hex(CLIP.private_key), "--activity", "ride", "--voice", "on"),
    ]
    run = subprocess.run(command, capture_output=True, text=True, check=False, timeout=300)
    assert run.returncode == 0, f"SIL exit {run.returncode}:\n{run.stderr}"
    data = out.read_bytes()
    return SilRun(ride, data, Session.from_bytes(data))


def test_the_clip_writes_a_complete_session_with_every_flag_signed(sil_run: SilRun) -> None:
    session = sil_run.session
    assert session.decoded.complete, session.decoded.issue
    header = session.header
    assert (header.device_id, header.session_id, header.simulated, header.trimmed) == (
        CLIP.device_id,
        SESSION_ID,
        True,
        False,
    )
    flags = session.of_type(Flag)
    assert flags, "the ride has presses: the Clip wrote no flag"
    public_key = CLIP.private_key.public_key()
    assert all(f.sig_alg == SigAlg.ECDSA_P256 for f in flags)
    assert all(verify_flag(public_key, header.device_id, header.session_id, f) for f in flags)


def _matches(expected_ms: Sequence[int], actual_ms: Sequence[int], tolerance_ms: int) -> list[int]:
    """The expected instants with no actual one within the tolerance."""
    return [t for t in expected_ms if not any(abs(t - a) <= tolerance_ms for a in actual_ms)]


def _outside_refractory(onsets_ms: Sequence[int], detected_ms: Sequence[int], refractory_ms: int) -> list[int]:
    """Onsets a detector must report: not inside the quiet period after an event it already reported."""
    return [t for t in onsets_ms if not any(0 < t - d < refractory_ms for d in detected_ms)]


def test_hard_brake_events_are_where_the_rider_braked(sil_run: SilRun) -> None:
    brakes = [b for b in sil_run.ride.readings.brakes if sil_run.in_session(b.t)]
    detected = sil_run.events(EventKind.HARD_BRAKE)
    assert detected, "the ride brakes hard: the Clip wrote no hard brake"
    # Every hard-brake EVENT starts while the rider was braking.
    braking = [(sil_run.at_ms(b.t), sil_run.at_ms(b.t + b.duration)) for b in brakes]
    stray = [t for t in detected if not any(s - _ONSET_TOLERANCE_MS <= t <= e for s, e in braking)]
    assert not stray, f"hard brakes where the rider did not brake: {stray}"
    # Every clear brake was reported (refractory periods aside).
    clear = [
        sil_run.at_ms(b.t)
        for b in brakes
        if b.mean >= DETECTION_HARD_BRAKE_MPS2 * _CLEARLY_ABOVE
        and b.duration * 1000 >= DETECTION_HARD_BRAKE_MIN_MS * _CLEARLY_ABOVE
    ]
    must_fire = _outside_refractory(clear, detected, DETECTION_HARD_BRAKE_REFRACTORY_MS)
    assert not _matches(must_fire, detected, _ONSET_TOLERANCE_MS)


def test_pothole_events_are_where_the_rider_hit_one(sil_run: SilRun) -> None:
    impacts = [i for i in sil_run.ride.readings.impacts if sil_run.in_session(i.t)]
    detected = sil_run.events(EventKind.POTHOLE)
    assert detected, "the ride hits potholes: the Clip wrote no pothole"
    assert not _matches(detected, [sil_run.at_ms(i.t) for i in impacts], _ONSET_TOLERANCE_MS), (
        "potholes where the rider hit nothing"
    )
    clear = [
        sil_run.at_ms(i.t)
        for i in impacts
        if i.rms >= DETECTION_POTHOLE_RMS_MPS2 * _CLEARLY_ABOVE
        and i.peak >= DETECTION_POTHOLE_PEAK_MPS2 * _CLEARLY_ABOVE
    ]
    must_fire = _outside_refractory(clear, detected, DETECTION_POTHOLE_REFRACTORY_MS)
    assert not _matches(must_fire, detected, _ONSET_TOLERANCE_MS)


def test_every_gesture_becomes_a_flag_or_an_undo(sil_run: SilRun) -> None:
    ride = sil_run.ride
    gestures = [g for g in ride.gestures if sil_run.in_session(g.t)]
    assert {g.kind for g in gestures} == set(GestureKind), "the ride should exercise press, hold and double press"

    expected: list[tuple[str, int, int, int]] = []  # (record, seq, source or 0, keyword or 0) in time order
    times: list[int] = []
    seq, undoable = 0, None
    for gesture in gestures:
        times.append(sil_run.at_ms(gesture.t))
        if gesture.kind is GestureKind.DOUBLE:
            assert undoable is not None, "a double press with nothing to undo"
            expected.append(("undo", undoable, 0, 0))
            undoable = None
            continue
        source, keyword = FlagSource.PRESS, HazardKind.NONE
        if gesture.kind is GestureKind.HOLD:
            source = FlagSource.VOICE
            heard = ride.readings.keywords.get(gesture)
            if heard is not None and heard.confidence >= BUTTON_KEYWORD_MIN_CONFIDENCE:
                keyword = heard.kind
        expected.append(("flag", seq, source, keyword))
        undoable, seq = seq, seq + 1

    records = sorted((*sil_run.session.of_type(Flag), *sil_run.session.of_type(FlagUndo)), key=lambda r: r.t_ms)
    actual = [("flag", r.seq, r.source, r.kind) if isinstance(r, Flag) else ("undo", r.seq, 0, 0) for r in records]
    assert actual == expected
    # A flag is dated at the press (once debounced); an undo when the double press is recognised.
    for (record, *_), t, r in zip(expected, times, records, strict=True):
        tolerance = BUTTON_DEBOUNCE_MS if record == "flag" else BUTTON_DOUBLE_PRESS_GAP_MS
        assert abs(sil_run.unix_ms(r.t_ms) - t) <= tolerance, f"{record} {r.seq} is {r.t_ms} ms into the session"


async def test_the_trimmed_ride_reaches_the_rider_feed(sil_run: SilRun, phone: Phone, api: httpx.AsyncClient) -> None:
    pairing = await phone.pair(CLIP, Athlete.for_rider(CLIP.rider_id, "e-bike"))
    result = await phone.sync(pairing, sil_run.data)
    assert result.trim.data is not None
    assert result.receipt is not None
    trimmed = Session.from_bytes(result.trim.data)
    assert trimmed.header.trimmed
    assert trimmed.trim is not None
    assert min(trimmed.trim.start_m, trimmed.trim.end_m) >= PRIVACY_TRIM_M
    kept = effective_flags(trimmed.records)
    receipt = result.receipt
    assert (receipt.duplicate, receipt.flags_accepted, receipt.flags_rejected) == (False, len(kept), 0)

    auth = {"Authorization": f"Bearer {pairing.token}"}
    feed = (await api.get("/v1/feed", headers=auth)).json()
    assert receipt.activity_id in [a["id"] for a in feed]
    activity = (await api.get(f"/v1/activities/{receipt.activity_id}", headers=auth)).json()
    assert activity["athleteId"] == CLIP.rider_id
    assert activity["type"] == "ride"
    assert [f["id"] for f in activity["flags"]] == [f"{receipt.activity_id}-f{f.seq}" for f in kept]
    clip_events = trimmed.of_type(Event)
    for kind, name in ((EventKind.HARD_BRAKE, "hard_brake"), (EventKind.POTHOLE, "pothole")):
        on_clip = sum(e.kind == kind for e in clip_events)
        assert sum(e["type"] == name for e in activity["events"]) == on_clip, name

    again = await phone.sync(pairing, sil_run.data)
    assert again.receipt is not None
    assert again.receipt.duplicate
    assert again.receipt.activity_id == receipt.activity_id
