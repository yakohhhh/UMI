from __future__ import annotations

import pytest
from umi_protocol import crc16_ccitt_false, crc32_iso_hdlc

CHECK_INPUT = b"123456789"


def test_crc16_ccitt_false_check_value() -> None:
    assert crc16_ccitt_false(CHECK_INPUT) == 0x29B1


def test_crc32_iso_hdlc_check_value() -> None:
    assert crc32_iso_hdlc(CHECK_INPUT) == 0xCBF43926


def test_crc_of_nothing_is_the_initial_value() -> None:
    assert crc16_ccitt_false(b"") == 0xFFFF
    assert crc32_iso_hdlc(b"") == 0


@pytest.mark.parametrize("split", range(len(CHECK_INPUT) + 1))
def test_crcs_can_run_over_a_stream(split: int) -> None:
    head, tail = CHECK_INPUT[:split], CHECK_INPUT[split:]
    assert crc16_ccitt_false(tail, crc16_ccitt_false(head)) == 0x29B1
    assert crc32_iso_hdlc(tail, crc32_iso_hdlc(head)) == 0xCBF43926
