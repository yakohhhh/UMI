from __future__ import annotations

import dataclasses
import struct
from collections.abc import Callable
from typing import Any

import pytest
from umi_protocol import (
    Activity,
    Air,
    EncodeError,
    End,
    Event,
    EventKind,
    Fix,
    FixedRecord,
    Flag,
    FlagSource,
    FlagUndo,
    HazardKind,
    Header,
    HeaderError,
    HeaderFlag,
    Lang,
    RecordType,
    Sample,
    SigAlg,
    State,
    Status,
    StatusFlag,
    TimeSync,
    Trim,
    UnknownRecord,
    crc32_iso_hdlc,
    format_device_id,
    parse_device_id,
)
from umi_protocol.constants import FORMAT_NOT_AVAILABLE_U16

NA = FORMAT_NOT_AVAILABLE_U16


def _flag(**changes: Any) -> Flag:
    base = Flag(1000, 0, FlagSource.PRESS, HazardKind.NONE, 0, Lang.NONE, 413900000, 21700000, 500, 900, 6500)
    return dataclasses.replace(base, **changes)


@pytest.mark.parametrize(
    ("cls", "size"),
    [
        (Sample, 24),
        (Air, 16),
        (Event, 20),
        (Flag, 94),
        (FlagUndo, 6),
        (Status, 12),
        (TimeSync, 12),
        (State, 6),
        (Trim, 8),
        (End, 16),
    ],
)
def test_payload_sizes_match_the_spec(cls: type[FixedRecord], size: int) -> None:
    assert cls.LAYOUT.size == size


def test_header_is_32_bytes_and_round_trips(header: Header) -> None:
    data = header.to_bytes()
    assert len(data) == 32
    assert data[:4] == b"UMIS"
    assert Header.from_bytes(data) == header


def test_header_layout_is_pinned() -> None:
    header = Header(
        header_flags=HeaderFlag.SIMULATED,
        device_id=0x00000000C11B0001,
        session_id=7,
        activity=Activity.RUN,
        hw_rev=3,
        fw_version=(1, 2, 3),
    )
    assert (
        header.to_bytes()[:28].hex()
        == "554d49530120" + "0100" + "01001bc100000000" + "07000000" + "0203" + "010203" + "000000"
    )


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        (lambda b: b"XMIS" + b[4:], "magic"),
        (lambda b: b[:4] + b"\x02" + b[5:], "format_version"),
        (lambda b: b[:5] + b"\x1f" + b[6:], "header_len"),
        (lambda b: b[:5] + b"\x40" + b[6:], "header_len"),
        (lambda b: b[:10] + bytes([b[10] ^ 1]) + b[11:], "CRC"),
        (lambda b: b[:20], "32-byte header"),
    ],
)
def test_bad_headers_are_refused(header: Header, patch: Callable[[bytes], bytes], message: str) -> None:
    with pytest.raises(HeaderError, match=message):
        Header.from_bytes(patch(header.to_bytes()))


def test_header_may_grow_within_v1(header: Header) -> None:
    body = bytearray(header.to_bytes()[:28])
    body[5] = 36  # header_len
    data = bytes(body) + crc32_iso_hdlc(body).to_bytes(4, "little") + b"ext!"
    assert Header.from_bytes(data) == header


def test_header_properties() -> None:
    header = Header(header_flags=HeaderFlag.SIMULATED | HeaderFlag.TRIMMED, device_id=0xC11B0001, session_id=1)
    assert header.simulated
    assert header.trimmed
    assert header.device_hex == "00000000c11b0001"


def test_device_id_text_form() -> None:
    assert format_device_id(0xC11B0001) == "00000000c11b0001"
    assert parse_device_id("00000000c11b0001") == parse_device_id("0xC11B0001") == 0xC11B0001
    with pytest.raises(ValueError, match="u64"):
        parse_device_id("1" + "0" * 16)


def test_sample_si_units() -> None:
    sample = Sample(1000, 413870123, 21700456, 500, 9050, 1250, 6543, 9, Fix.THREE_D, 12)
    assert sample.lat == pytest.approx(41.3870123)
    assert sample.lon == pytest.approx(2.1700456)
    assert sample.speed_kmh == pytest.approx(18.0)
    assert sample.heading_deg == pytest.approx(90.5)
    assert sample.vib_mps2 == pytest.approx(1.25)
    assert sample.noise_dba == pytest.approx(65.43)
    assert sample.hdop == pytest.approx(0.9)
    assert (sample.lat_e7, sample.speed_cms) == (413870123, 500)  # the raw integers stay


def test_missing_measurements_read_as_none() -> None:
    sample = Sample(1000, 0, 0, NA, NA, NA, NA, 255, Fix.NONE, 0)
    assert (sample.speed_kmh, sample.heading_deg, sample.vib_mps2, sample.noise_dba, sample.hdop) == (None,) * 5
    air = Air(1000, NA, NA, NA, -150, NA)
    assert (air.pm1_ugm3, air.pm25_ugm3, air.pm10_ugm3, air.rh_pct) == (None,) * 4
    assert air.temp_c == pytest.approx(-1.5)


@pytest.mark.parametrize(("fix", "has_fix"), [(0, False), (1, False), (2, True), (3, True), (4, True)])
def test_has_fix(fix: int, has_fix: bool) -> None:
    assert Sample(0, 0, 0, 0, 0, 0, 0, 0, fix, 0).has_fix is has_fix


def test_other_si_helpers() -> None:
    assert Air(0, 52, 87, 131, 1950, 612).pm25_ugm3 == pytest.approx(8.7)
    event = Event(0, EventKind.HARD_BRAKE, 3850, 6120, 640, 413900000, 21700000)
    assert [event.value_mps2, event.peak_mps2, event.lat] == pytest.approx([3.85, 6.12, 41.39])
    status = Status(0, 80, StatusFlag.CHARGING, 3980, 3125, 5120)
    assert [status.battery_v, status.board_temp_c] == pytest.approx([3.98, 31.25])
    flag = _flag()
    assert [flag.speed_kmh, flag.vib_mps2, flag.noise_dba] == pytest.approx([18.0, 0.9, 65.0])


def test_enum_values_decode_to_members_and_unknown_values_stay_ints() -> None:
    payload = bytearray(_flag().to_payload())
    payload[6] = 9  # a FlagSource value from a future firmware
    flag = Flag.from_payload(bytes(payload))
    assert flag.source == 9
    assert type(flag.source) is int
    assert flag.kind is HazardKind.NONE
    assert flag.to_payload() == bytes(payload)


def test_extra_payload_bytes_are_ignored() -> None:
    sample = Sample(1000, 1, 2, 3, 4, 5, 6, 7, Fix.TWO_D, 9)
    assert Sample.from_payload(sample.to_payload() + b"more") == sample


def test_reserved_bytes_are_written_as_zero() -> None:
    payload = _flag().to_payload()
    assert payload[10:12] == payload[26:28] == b"\0\0"
    assert Sample(0, 0, 0, 0, 0, 0, 0, 0, 0, 0).to_payload()[23] == 0


def test_out_of_range_values_name_the_field() -> None:
    with pytest.raises(EncodeError, match=r"Sample\.lat_e7 = 3000000000"):
        Sample(0, 3_000_000_000, 0, 0, 0, 0, 0, 0, 3, 0).to_payload()
    with pytest.raises(EncodeError, match=r"Air\.temp_cc"):
        Air(0, 0, 0, 0, 40_000, 0).to_payload()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"signature": bytes(63)}, "64 bytes"),
        ({"signature": b"\x01" * 64}, "zero-filled"),
        ({"sig_len": 64}, "zero-filled"),
        ({"sig_alg": SigAlg.ECDSA_P256, "sig_len": 0, "signature": b"\x01" * 64}, "sig_len 64"),
    ],
)
def test_flag_signature_fields_must_agree(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(EncodeError, match=message):
        _flag(**changes).to_payload()


def test_flag_signed_payload_is_the_first_28_bytes() -> None:
    flag = _flag()
    assert flag.signed_payload == flag.to_payload()[:28]
    assert not flag.is_signed


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (UnknownRecord(RecordType.SAMPLE, bytes(24)), "unassigned"),
        (UnknownRecord(RecordType.END, bytes(16)), "unassigned"),
        (UnknownRecord(256, bytes(4)), "unassigned"),
        (UnknownRecord(0x42, bytes(3)), "4..255"),
        (UnknownRecord(0x42, bytes(256)), "4..255"),
    ],
)
def test_unknown_records_must_be_unknown_and_framable(record: UnknownRecord, message: str) -> None:
    with pytest.raises(EncodeError, match=message):
        record.to_payload()


def test_unknown_record_t_ms() -> None:
    assert UnknownRecord(0x42, struct.pack("<I", 1234) + b"x").t_ms == 1234
