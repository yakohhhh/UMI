"""The golden vectors are what every other codec is tested against: they must never drift."""

from __future__ import annotations

import importlib.util
import json
import sys
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from umi_protocol import (
    RECORD_CLASSES,
    Flag,
    Session,
    Trim,
    decode_session,
    load_private_key_pem,
    load_public_key_pem,
    to_json,
    trim_session,
    verify_flag,
)

VECTORS_DIR = Path(__file__).resolve().parents[2] / "vectors"
SESSIONS = ["minimal", "full", "truncated", "unknown-record", "ride", "ride.trimmed"]


@cache
def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("umi_vectors_generate", VECTORS_DIR / "generate.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while the file runs
    spec.loader.exec_module(module)
    return module


@cache
def _regenerated() -> dict[str, bytes]:
    files: dict[str, bytes] = _generator().build(load_private_key_pem((VECTORS_DIR / "test-key.pem").read_bytes()))
    return files


def test_every_vector_is_committed() -> None:
    expected = {f"{name}{ext}" for name in SESSIONS for ext in (".umis", ".json")} | {"test-key.pub.pem"}
    assert set(_regenerated()) == expected


@pytest.mark.parametrize(
    "name", sorted({f"{n}{e}" for n in SESSIONS for e in (".umis", ".json")} | {"test-key.pub.pem"})
)
def test_regenerating_changes_no_byte(name: str) -> None:
    assert _regenerated()[name] == (VECTORS_DIR / name).read_bytes(), (
        f"protocol/vectors/{name} drifted: if the change is intended, run "
        "`uv run python protocol/vectors/generate.py` and review the diff"
    )


@pytest.mark.parametrize("name", SESSIONS)
def test_each_session_decodes_to_its_json(vectors_dir: Path, name: str) -> None:
    decoded = decode_session((vectors_dir / f"{name}.umis").read_bytes())
    committed = (vectors_dir / f"{name}.json").read_text()
    assert to_json(decoded) == committed
    assert json.loads(committed)["complete"] is (name != "truncated")


def test_ride_trimmed_is_the_trim_of_ride(vectors_dir: Path) -> None:
    result = trim_session((vectors_dir / "ride.umis").read_bytes())
    assert result.data == (vectors_dir / "ride.trimmed.umis").read_bytes()


@pytest.mark.parametrize("name", ["full", "ride", "ride.trimmed"])
def test_signed_flags_verify_with_the_test_key(
    vectors_dir: Path, test_key: ec.EllipticCurvePrivateKey, name: str
) -> None:
    public = load_public_key_pem((vectors_dir / "test-key.pub.pem").read_bytes())
    assert public.public_numbers() == test_key.public_key().public_numbers()
    session = Session.from_bytes((vectors_dir / f"{name}.umis").read_bytes())
    flags = session.of_type(Flag)
    verdicts = [verify_flag(public, session.header.device_id, session.header.session_id, f) for f in flags]
    assert verdicts == [f.is_signed for f in flags]
    assert any(verdicts)


def test_full_covers_every_record_type(vectors_dir: Path) -> None:
    session = Session.from_bytes((vectors_dir / "full.umis").read_bytes())
    present = {type(r) for r in session.records}
    assert present == set(RECORD_CLASSES.values()) - {Trim}
    assert session.decoded.end is not None
