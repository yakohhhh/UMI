"""The firmware, fed a scenario the simulator exported, records the session the virtual Clip records.

Runs the firmware's SIL program (``pio run -e sil`` in ``firmware/``) on the raw
sensor streams of a simulated ride and compares its ``.umis`` with the virtual
Clip's: the recorder's decisions, the flags (signed with the same key) and the
events must agree, within what the firmware's own signal processing moves
(debouncing, detection from the 100 Hz IMU, NMEA rounding). Skipped until the
SIL program is built.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from itertools import starmap
from pathlib import Path
from typing import NamedTuple

import pytest
from umi_protocol import (
    Air,
    Event,
    Flag,
    FlagUndo,
    Sample,
    Session,
    State,
    TimeSync,
    private_key_to_raw_hex,
    verify_flag,
)
from umi_protocol.constants import BUTTON_DEBOUNCE_MS, DETECTION_HARD_BRAKE_MIN_MS
from umi_sim.clip import ClipIdentity, VirtualClip
from umi_sim.rider import Vehicle
from umi_sim.scenario import write_scenario
from umi_sim.simulation import City, RideSpec, simulate

pytestmark = pytest.mark.e2e

_REPO = Path(__file__).resolve().parents[2]
PROGRAM = Path(os.environ.get("UMI_SIL_PROGRAM", _REPO / "firmware" / ".pio" / "build" / "sil" / "program"))
# NMEA carries minutes with 5 decimals: about 2e-7 degrees.
_POSITION_E7 = 2


def _firmware_session(spec: RideSpec, city: City, identity: ClipIdentity, tmp_path: Path) -> tuple[Session, Session]:
    """The virtual Clip's session and the firmware's for the same ride."""
    ride = simulate(city, spec)
    recording = VirtualClip(identity).record(ride)
    scenario, out = tmp_path / "scenario.txt", tmp_path / "firmware.umis"
    with scenario.open("w", encoding="utf-8", newline="\n") as file:
        write_scenario(ride, file, title="e2e")
    command = [
        str(PROGRAM),
        *("--scenario", str(scenario), "--out", str(out)),
        *("--device-id", identity.device_hex, "--session-id", str(recording.session_id)),
        *("--activity", spec.vehicle.activity.name.lower(), "--key-hex", private_key_to_raw_hex(identity.private_key)),
        *("--voice", "on" if spec.habits.voice else "off"),
    ]
    run = subprocess.run(command, capture_output=True, text=True, check=False, timeout=120)
    assert run.returncode == 0, run.stderr
    return Session.from_bytes(recording.data), Session.from_bytes(out.read_bytes())


class Case(NamedTuple):
    origin: str
    destination: str
    vehicle: Vehicle
    seed: int


CASES = [
    Case("Gràcia", "22@", Vehicle.E_BIKE, 2),
    Case("Sant Antoni", "Glòries", Vehicle.SCOOTER, 5),
    Case("Poblenou", "Bogatell", Vehicle.RUN, 0),
]


@pytest.mark.skipif(not PROGRAM.is_file(), reason=f"firmware SIL not built ({PROGRAM}): pio run -e sil")
@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c.vehicle}-{c.origin}-{c.destination}")
def test_firmware_records_the_same_session(
    city: City, make_spec: Callable[..., RideSpec], identity: ClipIdentity, tmp_path: Path, case: Case
) -> None:
    vehicle = case.vehicle
    spec = make_spec(case.origin, case.destination, vehicle=vehicle, seed=case.seed)
    sim, fw = _firmware_session(spec, city, identity, tmp_path)

    assert fw.decoded.complete
    assert (fw.header.device_id, fw.header.session_id, fw.header.activity, fw.header.simulated) == (
        sim.header.device_id,
        sim.header.session_id,
        sim.header.activity,
        sim.header.simulated,
    )
    assert fw.duration_ms == sim.duration_ms
    assert fw.of_type(State) == sim.of_type(State)
    assert fw.of_type(TimeSync) == sim.of_type(TimeSync)

    samples = list(zip(sim.of_type(Sample), fw.of_type(Sample), strict=True))
    assert all(a.t_ms == b.t_ms and a.fix == b.fix for a, b in samples)
    assert all(
        abs(a.lat_e7 - b.lat_e7) <= _POSITION_E7 and abs(a.lon_e7 - b.lon_e7) <= _POSITION_E7 for a, b in samples
    )

    def same_air(a: Air, b: Air) -> bool:
        pairs = ((a.pm1_dug, b.pm1_dug), (a.pm25_dug, b.pm25_dug), (a.pm10_dug, b.pm10_dug), (a.rh_dpct, b.rh_dpct))
        return a.t_ms == b.t_ms and all(abs(x - y) <= 1 for x, y in pairs)

    assert all(starmap(same_air, zip(sim.of_type(Air), fw.of_type(Air), strict=True)))

    flags = list(zip(sim.of_type(Flag), fw.of_type(Flag), strict=True))
    # The rider's press is the first contact; the firmware stamps it once the debouncer has settled.
    assert all(abs(b.t_ms - a.t_ms) <= BUTTON_DEBOUNCE_MS for a, b in flags)
    assert all((a.seq, a.source, a.kind, a.lang) == (b.seq, b.source, b.kind, b.lang) for a, b in flags)
    public = identity.private_key.public_key()
    assert all(verify_flag(public, fw.header.device_id, fw.header.session_id, b) for _, b in flags)
    assert [u.seq for u in fw.of_type(FlagUndo)] == [u.seq for u in sim.of_type(FlagUndo)]

    if vehicle is not Vehicle.RUN:
        # Runs record no events by design (no surface data for runners); the firmware's
        # pothole detector has no activity gate yet, so it is only compared on rides.
        events = list(zip(sim.of_type(Event), fw.of_type(Event), strict=True))
        assert all(a.kind == b.kind for a, b in events)
        assert all(abs(a.t_ms - b.t_ms) <= DETECTION_HARD_BRAKE_MIN_MS for a, b in events)
