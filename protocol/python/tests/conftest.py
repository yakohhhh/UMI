from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from umi_protocol import Activity, Fix, Header, HeaderFlag, Sample, load_private_key_pem

VECTORS_DIR = Path(__file__).resolve().parents[2] / "vectors"

# Each step north is 900e-7 degrees of latitude, about 10.01 m.
STEP_E7 = 900
START_LAT_E7 = 413_900_000
START_LON_E7 = 21_700_000


@pytest.fixture(scope="session")
def vectors_dir() -> Path:
    return VECTORS_DIR


@pytest.fixture(scope="session")
def test_key() -> ec.EllipticCurvePrivateKey:
    return load_private_key_pem((VECTORS_DIR / "test-key.pem").read_bytes())


@pytest.fixture
def header() -> Header:
    return Header(
        header_flags=HeaderFlag.SIMULATED,
        device_id=0x0123456789ABCDEF,
        session_id=42,
        activity=Activity.RIDE,
        fw_version=(1, 2, 3),
    )


@pytest.fixture
def straight_ride() -> Callable[[int], list[Sample]]:
    """``n`` one-second samples riding due north in Barcelona, about 10 m apart."""

    def build(n: int) -> list[Sample]:
        return [
            Sample(1000 * (i + 1), START_LAT_E7 + STEP_E7 * i, START_LON_E7, 1000, 0, 900, 6500, 8, Fix.THREE_D, 12)
            for i in range(n)
        ]

    return build
