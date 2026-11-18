from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from umi_protocol import generate_private_key, public_key_to_pem
from umi_protocol.__main__ import EXIT_INVALID, EXIT_NOTHING_TO_UPLOAD, EXIT_OK, main


def test_inspect_prints_a_summary(vectors_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(vectors_dir / "full.umis")]) == EXIT_OK
    out = capsys.readouterr().out
    assert "00000000c11b0001 · session 1 · ride" in out
    assert "status    complete" in out
    assert "flag #1   0:00:04  voice roadworks (92 %, ca)  [signed]" in out
    assert "[unsigned, undone]" in out


def test_inspect_json(vectors_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", "--json", str(vectors_dir / "ride.trimmed.umis")]) == EXIT_OK
    summary = json.loads(capsys.readouterr().out)
    assert summary["complete"] is True
    assert summary["header"]["device_id"] == "00000000c11b0001"
    assert summary["trim"] == {"start_m": 202, "end_m": 200}
    assert summary["records"]["trim"] == 1
    assert summary["started_at"] == "2026-11-18T07:52:00.000+00:00"
    assert [f["seq"] for f in summary["flags"]] == [1, 2, 3, 4]
    assert [f["undone"] for f in summary["flags"]] == [False, False, True, True]


def test_inspect_reports_a_session_cut_short(vectors_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(vectors_dir / "truncated.umis")]) == EXIT_OK
    assert "incomplete: record at byte 104 fails its CRC" in capsys.readouterr().out


def test_decode_prints_the_canonical_json(vectors_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["decode", str(vectors_dir / "unknown-record.umis")]) == EXIT_OK
    assert capsys.readouterr().out == (vectors_dir / "unknown-record.json").read_text()


def test_trim_writes_the_trimmed_session(vectors_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out.umis"
    assert main(["trim", str(vectors_dir / "ride.umis"), str(out)]) == EXIT_OK
    assert out.read_bytes() == (vectors_dir / "ride.trimmed.umis").read_bytes()
    assert "trimmed 202 m + 200 m" in capsys.readouterr().out


def test_trim_of_a_short_trip_writes_nothing(
    vectors_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.umis"
    assert main(["trim", str(vectors_dir / "minimal.umis"), str(out)]) == EXIT_NOTHING_TO_UPLOAD
    assert not out.exists()
    assert "nothing to upload" in capsys.readouterr().err


def test_trim_refuses_a_trimmed_session(vectors_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["trim", str(vectors_dir / "ride.trimmed.umis"), str(tmp_path / "x.umis")]) == EXIT_INVALID
    assert "already trimmed" in capsys.readouterr().err


def test_verify(vectors_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pubkey = str(vectors_dir / "test-key.pub.pem")
    assert main(["verify", str(vectors_dir / "ride.trimmed.umis"), "--pubkey", pubkey]) == EXIT_OK
    assert "4/4 flags verified" in capsys.readouterr().out

    assert main(["verify", str(vectors_dir / "full.umis"), "--pubkey", pubkey]) == EXIT_INVALID
    assert "flag #2   0:00:04  unsigned" in capsys.readouterr().out

    other: ec.EllipticCurvePublicKey = generate_private_key().public_key()
    (tmp_path / "other.pem").write_bytes(public_key_to_pem(other))
    assert main(["verify", str(vectors_dir / "full.umis"), "--pubkey", str(tmp_path / "other.pem")]) == EXIT_INVALID
    assert "BAD SIGNATURE" in capsys.readouterr().out


def test_invalid_input_is_reported_without_a_traceback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junk = tmp_path / "junk.umis"
    junk.write_bytes(b"not a session log at all, just text")
    assert main(["inspect", str(junk)]) == EXIT_INVALID
    assert "bad magic" in capsys.readouterr().err
    assert main(["inspect", str(tmp_path / "missing.umis")]) == EXIT_INVALID


def test_runs_as_a_module(vectors_dir: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "umi_protocol", "inspect", "--json", str(vectors_dir / "minimal.umis")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(done.stdout)["records"] == {"sample": 3, "time_sync": 1}
