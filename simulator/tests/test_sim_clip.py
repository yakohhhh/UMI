from __future__ import annotations

import os
import stat
from collections.abc import Callable
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import pytest
from umi_protocol import (
    Activity,
    Air,
    Event,
    Flag,
    FlagSource,
    FlagUndo,
    HazardKind,
    RecorderState,
    Sample,
    Session,
    State,
    Status,
    TimeSync,
    generate_private_key,
    verify_flag,
)
from umi_protocol.constants import (
    BUTTON_KEYWORD_MIN_CONFIDENCE,
    DETECTION_AUTO_PAUSE_S,
    DETECTION_AUTO_STOP_S,
    RATES_AIR_PERIOD_S,
    RATES_STATUS_PERIOD_S,
)
from umi_sim.clip import ClipIdentity, KeyStore, Recording, UnknownClipError, VirtualClip
from umi_sim.rider import Vehicle
from umi_sim.simulation import City, RideSpec, SimulatedRide, simulate


@pytest.fixture(scope="module")
def session(recording: Recording) -> Session:
    return Session.from_bytes(recording.data)


def test_session_is_a_complete_simulated_log(session: Session, recording: Recording, identity: ClipIdentity) -> None:
    header = session.header
    assert session.decoded.complete
    assert header.simulated
    assert not header.trimmed
    assert header.device_id == identity.device_id
    assert header.session_id == recording.session_id
    assert header.activity is Activity.RIDE
    assert header.fw_version == (0, 1, 0)
    assert header.hw_rev == 0
    assert session.duration_ms == recording.duration_ms


def test_records_are_in_time_order_and_start_recording(session: Session) -> None:
    times = [r.t_ms for r in session.records]
    assert times == sorted(times)
    assert session.records[0] == State(0, RecorderState.RECORDING)


def test_time_sync_places_the_session(session: Session, commute: SimulatedRide, recording: Recording) -> None:
    (sync,) = session.of_type(TimeSync)
    # The firmware reads the fix that starts the session before the session exists: it syncs on the next one.
    assert sync.t_ms == 1000
    assert session.started_at == recording.started_at
    assert commute.depart_utc < recording.started_at < commute.utc(60)


def test_periodic_records_follow_the_rates(session: Session) -> None:
    samples = [s.t_ms for s in session.of_type(Sample)]
    assert samples[0] == 1000
    assert all(t % 1000 == 0 for t in samples)
    assert [a.t_ms for a in session.of_type(Air)] == list(
        range(RATES_AIR_PERIOD_S * 1000, session.duration_ms, RATES_AIR_PERIOD_S * 1000)
    )
    assert [s.t_ms for s in session.of_type(Status)] == list(
        range(0, session.duration_ms, RATES_STATUS_PERIOD_S * 1000)
    )


def test_recorder_pauses_resumes_and_stops_like_the_firmware(session: Session) -> None:
    states = session.of_type(State)
    pauses = [s for s in states if s.state is RecorderState.AUTO_PAUSE]
    resumes = [s for s in states if s.state is RecorderState.RESUME]
    assert pauses
    assert len(resumes) == len(pauses) - 1
    assert [s.state for s in states[1:]] == [RecorderState.AUTO_PAUSE, RecorderState.RESUME] * len(resumes) + [
        RecorderState.AUTO_PAUSE
    ]
    samples = [s.t_ms for s in session.of_type(Sample)]
    for pause, resume in zip(pauses, resumes, strict=False):
        assert not [t for t in samples if pause.t_ms <= t <= resume.t_ms]
    # Paused 30 s after stopping, ended 300 s after stopping.
    assert session.duration_ms - pauses[-1].t_ms == (DETECTION_AUTO_STOP_S - DETECTION_AUTO_PAUSE_S) * 1000
    assert samples[-1] < pauses[-1].t_ms


def test_every_flag_is_signed_by_this_clip(session: Session, identity: ClipIdentity) -> None:
    flags = session.of_type(Flag)
    assert flags
    public = identity.private_key.public_key()
    assert all(verify_flag(public, identity.device_id, session.header.session_id, f) for f in flags)
    other = generate_private_key().public_key()
    assert not any(verify_flag(other, identity.device_id, session.header.session_id, f) for f in flags)
    assert [f.seq for f in flags] == list(range(len(flags)))


def test_flags_follow_the_button_rules(city: City, make_spec: Callable[..., RideSpec], identity: ClipIdentity) -> None:
    clip = VirtualClip(identity)
    sessions = [Session.from_bytes(clip.record(simulate(city, make_spec(seed=s))).data) for s in range(12)]
    flags = [f for s in sessions for f in s.of_type(Flag)]
    assert {f.source for f in flags} == {FlagSource.PRESS, FlagSource.VOICE}
    for flag in flags:
        assert flag.lat_e7 != 0
        assert flag.lon_e7 != 0
        if flag.source is FlagSource.PRESS:
            assert (flag.kind, flag.confidence) == (HazardKind.NONE, 0)
        elif flag.kind != HazardKind.NONE:
            assert flag.confidence >= BUTTON_KEYWORD_MIN_CONFIDENCE
    assert any(f.source is FlagSource.VOICE and f.kind != HazardKind.NONE for f in flags)
    undos = [(s, u) for s in sessions for u in s.of_type(FlagUndo)]
    assert undos
    for s, undo in undos:
        # A double press cancels the latest flag before it, once.
        before = [f for f in s.of_type(Flag) if f.t_ms <= undo.t_ms]
        assert undo.seq == before[-1].seq
        assert undo.seq not in {f.seq for f in s.flags}
    assert all(len({u.seq for u in s.of_type(FlagUndo)}) == len(s.of_type(FlagUndo)) for s in sessions)


def test_runs_shake_the_clip_but_record_no_events(
    city: City, make_spec: Callable[..., RideSpec], identity: ClipIdentity
) -> None:
    spec = make_spec("Poblenou", "Bogatell", vehicle=Vehicle.RUN)
    session = Session.from_bytes(VirtualClip(identity).record(simulate(city, spec)).data)
    assert session.header.activity is Activity.RUN
    assert not session.of_type(Event)
    running = [s.vib_mps2 for s in session.of_type(Sample) if s.speed_kmh is not None and s.speed_kmh > 6]
    assert running
    assert all(v is not None and v > 3.0 for v in running)


def test_same_ride_same_bytes(commute: SimulatedRide, identity: ClipIdentity, recording: Recording) -> None:
    assert VirtualClip(identity).record(commute).data == recording.data


def test_session_id_is_the_start_minute() -> None:
    first = VirtualClip.session_id_for(datetime(2026, 11, 18, 6, 50, 8, tzinfo=UTC))
    assert first == VirtualClip.session_id_for(datetime(2026, 11, 18, 6, 50, 59, tzinfo=UTC))
    assert VirtualClip.session_id_for(datetime(2026, 11, 18, 6, 51, tzinfo=UTC)) == first + 1
    assert 0 < first < 2**32


def test_status_reports_battery_and_storage(session: Session) -> None:
    statuses = session.of_type(Status)
    assert all(10 <= s.board_temp_c <= 40 for s in statuses)
    assert [s.battery_pct for s in statuses] == sorted((s.battery_pct for s in statuses), reverse=True)
    assert all(3500 < s.battery_mv < 4200 for s in statuses)
    assert all(b.free_kib <= a.free_kib for a, b in pairwise(statuses))


def test_keystore_provisions_once_and_keeps_the_key(tmp_path: Path) -> None:
    store = KeyStore(tmp_path / "keys")
    clip = store.clip_for("sim-0042")
    again = KeyStore(tmp_path / "keys").clip_for("sim-0042")
    assert again.device_id == clip.device_id
    assert again.public_key_pem == clip.public_key_pem
    assert clip.serial == "UMI-SIM-0042"
    assert store.find(clip.device_id).rider_id == "sim-0042"
    with pytest.raises(UnknownClipError):
        store.find(clip.device_id ^ 1)
    if os.name == "posix":
        assert stat.S_IMODE((tmp_path / "keys" / "sim-0042.key.pem").stat().st_mode) == 0o600


def test_keystore_skips_other_files_and_reports_broken_clips(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    clip = store.clip_for("sim-0001")
    (tmp_path / "package.json").write_text('{"name": "not a clip"}', encoding="utf-8")
    assert store.find(clip.device_id).rider_id == "sim-0001"
    (tmp_path / "sim-0001.json").write_text("{}", encoding="utf-8")
    with pytest.raises(UnknownClipError, match="not a readable simulated Clip"):
        store.clip_for("sim-0001")


@pytest.mark.parametrize("rider_id", ["", "Sim-0001", "../etc", "sim 0001", "a" * 40])
def test_keystore_refuses_unsafe_rider_ids(tmp_path: Path, rider_id: str) -> None:
    with pytest.raises(ValueError, match="rider id"):
        KeyStore(tmp_path).clip_for(rider_id)
