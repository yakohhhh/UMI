from __future__ import annotations

import io
import struct
from collections.abc import Callable

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from umi_protocol import (
    Air,
    Event,
    EventKind,
    Fix,
    Flag,
    FlagSource,
    FlagUndo,
    HazardKind,
    Header,
    HeaderFlag,
    Lang,
    PathPoint,
    Record,
    RecorderState,
    RecordType,
    Sample,
    SessionWriter,
    State,
    Status,
    StatusFlag,
    TimeSync,
    Trim,
    TrimError,
    TrimWindow,
    UnknownRecord,
    crc32_iso_hdlc,
    decode_session,
    encode_session,
    plan_trim,
    read_frames,
    sign_flag,
    trim_session,
    verify_flag,
)

RideBuilder = Callable[[int], list[Sample]]
START_UNIX_MS = 1_794_988_320_000


def _path(*distances: float) -> list[PathPoint]:
    return [
        PathPoint(Sample(1000 * i, 0, 0, 0, 0, 0, 0, 0, Fix.THREE_D, 0), d) for i, d in enumerate(distances, start=1)
    ]


# ---------------------------------------------------------------- where the trim cuts


def test_samples_exactly_200_m_from_either_end_are_kept() -> None:
    window = plan_trim(_path(0, 100, 200, 300, 400, 500, 600))
    assert window == TrimWindow(t_start=3000, t_end=5000, start_m=200, end_m=200)


def test_samples_just_short_of_200_m_are_cut() -> None:
    window = plan_trim(_path(0, 100, 199.999, 300, 400.001, 500, 600))
    assert window == TrimWindow(t_start=4000, t_end=4000, start_m=300, end_m=300)


def test_a_trip_of_exactly_500_m_is_uploaded() -> None:
    assert plan_trim(_path(0, 250, 500)) == TrimWindow(t_start=2000, t_end=2000, start_m=250, end_m=250)


def test_a_trip_under_500_m_is_not() -> None:
    assert plan_trim(_path(0, 250, 499.999)) is None
    assert plan_trim([]) is None


def test_fixes_too_sparse_to_keep_anything() -> None:
    assert plan_trim(_path(0, 600)) is None


def test_metres_removed_are_floored_and_fit_a_u16() -> None:
    assert plan_trim(_path(0, 200.9, 401.8, 602.7)) == TrimWindow(2000, 3000, start_m=200, end_m=200)
    assert plan_trim(_path(0, 70_000, 140_000)) == TrimWindow(2000, 2000, start_m=65535, end_m=65535)


# ---------------------------------------------------------------- what the trim keeps


def test_a_short_trip_uploads_nothing(header: Header, straight_ride: RideBuilder) -> None:
    result = trim_session(encode_session(header, straight_ride(40)))  # about 390 m
    assert result.data is None
    assert result.total_m == pytest.approx(39 * 10.0076, abs=0.01)
    assert result.reason is not None
    assert "500 m" in result.reason


def test_sparse_fixes_upload_nothing(header: Header, straight_ride: RideBuilder) -> None:
    samples = straight_ride(61)
    result = trim_session(encode_session(header, [samples[0], samples[-1]]))  # 600 m in one hop
    assert result.data is None
    assert result.reason is not None
    assert "200 m" in result.reason


def _flag(sample: Sample, t_ms: int, seq: int) -> Flag:
    return Flag(t_ms, seq, FlagSource.PRESS, HazardKind.NONE, 0, Lang.NONE, sample.lat_e7, sample.lon_e7, 0, 0, 0)


def _ride_with_extras(header: Header, samples: list[Sample], key: ec.EllipticCurvePrivateKey) -> list[Record]:
    """101 samples (about 1 km) plus every other record type, inside and outside the kept window.

    With 10.0076 m per second the window is t = 21000..81000 ms.
    """
    by_t = {s.t_ms: s for s in samples}

    def signed(t_ms: int, seq: int) -> Flag:
        return sign_flag(key, header.device_id, header.session_id, _flag(by_t[t_ms - t_ms % 1000], t_ms, seq))

    extras: list[Record] = [
        State(0, RecorderState.RECORDING),
        TimeSync(500, START_UNIX_MS + 500),
        UnknownRecord(0x42, struct.pack("<I", 2000) + b"near home"),
        Status(5000, 80, StatusFlag(0), 3980, 2400, 7000),
        Air(10_000, 50, 80, 120, 1500, 650),
        signed(10_300, 0),
        FlagUndo(10_800, 0),
        Event(15_000, EventKind.POTHOLE, 4200, 12500, 90, samples[14].lat_e7, samples[14].lon_e7),
        Air(30_000, 50, 80, 120, 1500, 650),
        Event(40_000, EventKind.HARD_BRAKE, 3500, 5100, 800, samples[39].lat_e7, samples[39].lon_e7),
        signed(50_300, 1),
        UnknownRecord(0x42, struct.pack("<I", 60_000) + b"mid ride"),
        signed(80_300, 2),
        FlagUndo(85_000, 2),  # after the window, but its flag is kept
        signed(95_300, 3),
        Status(95_500, 79, StatusFlag(0), 3975, 2410, 6990),
    ]
    return sorted([*samples, *extras], key=lambda r: r.t_ms)


def test_trim_keeps_the_middle_of_the_trip(
    header: Header, straight_ride: RideBuilder, test_key: ec.EllipticCurvePrivateKey
) -> None:
    records = _ride_with_extras(header, straight_ride(101), test_key)
    source = encode_session(header, records, duration_ms=400_000)
    result = trim_session(source)
    assert result.data is not None
    assert (result.start_m, result.end_m) == (200, 200)
    assert result.total_m == pytest.approx(1000.76, abs=0.01)

    trimmed = decode_session(result.data)
    assert trimmed.complete
    assert trimmed.header.header_flags == HeaderFlag.SIMULATED | HeaderFlag.TRIMMED
    assert trimmed.records[0] == Trim(t_ms=0, start_m=200, end_m=200)
    assert trimmed.end is not None
    assert (trimmed.end.t_ms, trimmed.end.record_count) == (400_000, len(trimmed.records))

    def in_window(r: Record) -> bool:
        return 21_000 <= r.t_ms <= 81_000

    expected = [
        r
        for r in records
        if isinstance(r, TimeSync | Status) or in_window(r) or (isinstance(r, FlagUndo) and r.seq == 2)
    ]
    assert list(trimmed.records[1:]) == expected
    assert [f.seq for f in trimmed.records if isinstance(f, Flag)] == [1, 2]
    assert result.dropped == {
        RecordType.SAMPLE: 40,
        RecordType.STATE: 1,
        0x42: 1,
        RecordType.AIR: 1,
        RecordType.FLAG: 2,
        RecordType.FLAG_UNDO: 1,
        RecordType.EVENT: 1,
    }


def test_flag_signatures_still_verify_after_the_trim(
    header: Header, straight_ride: RideBuilder, test_key: ec.EllipticCurvePrivateKey
) -> None:
    result = trim_session(encode_session(header, _ride_with_extras(header, straight_ride(101), test_key)))
    assert result.data is not None
    flags = [r for r in decode_session(result.data).records if isinstance(r, Flag)]
    assert flags
    assert all(verify_flag(test_key.public_key(), header.device_id, header.session_id, f) for f in flags)


def test_payloads_are_copied_byte_for_byte(header: Header, straight_ride: RideBuilder) -> None:
    samples = straight_ride(101)
    buffer = io.BytesIO()
    writer = SessionWriter(buffer, header)
    for sample in samples:
        extra = b"\x01\x02\x03\x04" if sample.t_ms == 50_000 else b""
        writer.append_frame(RecordType.SAMPLE, sample.to_payload() + extra)
    writer.finalize()
    result = trim_session(buffer.getvalue())
    assert result.data is not None
    source_frames = {f.t_ms: f.payload for f in read_frames(buffer.getvalue()).frames}
    for frame in read_frames(result.data).frames[1:]:
        assert frame.payload == source_frames[frame.t_ms]
    assert len(source_frames[50_000]) == 28


def test_a_session_cut_short_is_trimmed_and_closed(header: Header, straight_ride: RideBuilder) -> None:
    result = trim_session(encode_session(header, straight_ride(101), end=False))
    assert result.data is not None
    trimmed = decode_session(result.data)
    assert trimmed.complete
    assert trimmed.end is not None
    assert trimmed.end.t_ms == 101_000


def test_trimming_twice_is_refused(header: Header, straight_ride: RideBuilder) -> None:
    result = trim_session(encode_session(header, straight_ride(101)))
    assert result.data is not None
    with pytest.raises(TrimError, match="already trimmed"):
        trim_session(result.data)


def test_the_header_extension_survives_the_trim(header: Header, straight_ride: RideBuilder) -> None:
    session = encode_session(header, straight_ride(101))
    body = bytearray(session[:28])
    body[5] = 36
    # The extended header, then the records without END: trim accepts a session cut short.
    grown = bytes(body) + crc32_iso_hdlc(body).to_bytes(4, "little") + b"ext!" + session[32:-20]
    result = trim_session(grown)
    assert result.data is not None
    assert result.data[32:36] == b"ext!"
    assert decode_session(result.data).header.trimmed
