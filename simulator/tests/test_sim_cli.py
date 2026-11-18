from __future__ import annotations

import json
from pathlib import Path

import respx
from typer.testing import CliRunner
from umi_protocol import Session
from umi_sim.cli import app
from umi_sim.scenario import HEADER

RIDE = ["--from", "Gràcia", "--to", "22@", "--at", "2026-11-18T07:50", "--rider", "sim-0001"]
runner = CliRunner()


def test_places_and_network() -> None:
    places = runner.invoke(app, ["places"])
    assert places.exit_code == 0
    assert "22@" in places.output
    assert "Llacuna × Pallars" in places.output
    network = runner.invoke(app, ["network"])
    assert network.exit_code == 0
    assert "of 335 segments" in network.output


def test_ride_writes_the_session_the_clip_records(tmp_path: Path) -> None:
    out, keys = tmp_path / "ride.umis", tmp_path / "keys"
    result = runner.invoke(app, ["ride", *RIDE, "--out", str(out), "--keys", str(keys)])
    assert result.exit_code == 0, result.output
    session = Session.from_bytes(out.read_bytes())
    clip = json.loads((keys / "sim-0001.json").read_text())
    assert session.header.device_hex == clip["deviceId"]
    assert session.header.simulated
    assert session.started_at is not None
    assert session.started_at.hour == 6
    assert "the phone trims" in result.output
    # Same rider, same Clip, same seed: the same bytes.
    runner.invoke(app, ["ride", *RIDE, "--out", str(tmp_path / "again.umis"), "--keys", str(keys)])
    assert (tmp_path / "again.umis").read_bytes() == out.read_bytes()


def test_unknown_places_and_times_are_usage_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ride", "--from", "Gracai", "--to", "22@", "--keys", str(tmp_path)])
    assert result.exit_code == 2
    assert "Did you mean Gràcia" in result.output
    result = runner.invoke(app, ["ride", "--from", "Gràcia", "--to", "22@", "--at", "8am", "--keys", str(tmp_path)])
    assert result.exit_code == 2
    assert "ISO 8601" in result.output


def test_scenario_writes_raw_sensor_streams(tmp_path: Path) -> None:
    out = tmp_path / "scenario.txt"
    result = runner.invoke(app, ["scenario", *RIDE, "--out", str(out)])
    assert result.exit_code == 0, result.output
    first, second, third = out.read_text(encoding="utf-8").splitlines()[:3]
    assert first == HEADER
    assert "route=Gràcia → 22@" in second
    assert third.startswith("0,")


def test_upload_plays_the_phone(tmp_path: Path) -> None:
    keys = tmp_path / "keys"
    file = tmp_path / "ride.umis"
    runner.invoke(app, ["ride", *RIDE, "--out", str(file), "--keys", str(keys)])
    receipt = {"activityId": "act-9", "segmentsMatched": 9, "flags": {"accepted": 1, "rejected": 0}, "events": 1}
    with respx.mock(base_url="http://umi.test") as backend:
        backend.post("/v1/dev/devices").respond(201, json={"deviceId": "d", "athleteId": "sim-0001", "token": "t"})
        upload = backend.post("/v1/ingest/sessions").respond(201, json=receipt)
        result = runner.invoke(app, ["upload", str(file), "--api", "http://umi.test", "--keys", str(keys)])
    assert result.exit_code == 0, result.output
    assert "activity act-9 (created)" in result.output
    assert Session.from_bytes(upload.calls.last.request.content).header.trimmed


def test_upload_needs_a_known_clip(tmp_path: Path) -> None:
    file = tmp_path / "ride.umis"
    runner.invoke(app, ["ride", *RIDE, "--out", str(file), "--keys", str(tmp_path / "keys")])
    result = runner.invoke(app, ["upload", str(file), "--api", "http://umi.test", "--keys", str(tmp_path / "other")])
    assert result.exit_code == 1
    assert "no simulated Clip" in result.output


def test_fleet_writes_files(tmp_path: Path) -> None:
    out = tmp_path / "fleet"
    args = ["fleet", "--riders", "2", "--days", "2", "--start", "2026-11-16", "--seed", "7"]
    result = runner.invoke(app, [*args, "--out", str(out), "--keys", str(tmp_path / "keys")])
    assert result.exit_code == 0, result.output
    assert "rides for 2 riders from 2026-11-16 to 2026-11-17" in result.output
    assert list(out.rglob("*.umis"))
