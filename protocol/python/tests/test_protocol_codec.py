from __future__ import annotations

import dataclasses
import io
import re
import struct
import zlib
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from umi_protocol import (
    RECORD_CLASSES,
    Activity,
    EncodeError,
    End,
    FixedRecord,
    Flag,
    Header,
    HeaderError,
    HeaderFlag,
    ProtocolError,
    Record,
    RecordError,
    RecordType,
    Sample,
    SessionWriter,
    SigAlg,
    TimeSync,
    Trim,
    UnknownRecord,
    crc16_ccitt_false,
    decode_session,
    encode_frame,
    encode_session,
    read_frames,
)

HEADER = Header(header_flags=HeaderFlag.SIMULATED, device_id=0xC11B0001, session_id=1, activity=Activity.RIDE)
TRIMMED_HEADER = Header(header_flags=HeaderFlag.TRIMMED, device_id=0xC11B0001, session_id=1)

# ---------------------------------------------------------------- strategies

_INT_RANGES = {
    "B": (0, 2**8 - 1),
    "H": (0, 2**16 - 1),
    "I": (0, 2**32 - 1),
    "h": (-(2**15), 2**15 - 1),
    "i": (-(2**31), 2**31 - 1),
    "q": (-(2**63), 2**63 - 1),
}


def _wire_values(cls: type[FixedRecord]) -> list[st.SearchStrategy[Any]]:
    """A strategy per field, from the struct codes of the record's layout."""
    out: list[st.SearchStrategy[Any]] = []
    for count, code in re.findall(r"(\d*)([a-zA-Z])", cls.LAYOUT.format):
        if code == "s":
            out.append(st.binary(min_size=int(count), max_size=int(count)))
        elif code != "x":
            out.append(st.integers(*_INT_RANGES[code]))
    return out


def _fixed(cls: type[FixedRecord]) -> st.SearchStrategy[FixedRecord]:
    return st.builds(cls, *_wire_values(cls))


@st.composite
def _flags(draw: st.DrawFn) -> Flag:
    unsigned = Flag(*[draw(s) for s in _wire_values(Flag)[:-3]])
    if draw(st.booleans()):
        return unsigned
    signature = draw(st.binary(min_size=64, max_size=64))
    return dataclasses.replace(unsigned, sig_alg=SigAlg.ECDSA_P256, sig_len=64, signature=signature)


_unknown_records = st.builds(
    UnknownRecord,
    st.integers(0, 255).filter(lambda t: t not in RECORD_CLASSES and t != RecordType.END),
    st.binary(min_size=4, max_size=255),
)

# TRIM only appears first in a trimmed session, so it gets its own test.
_record_strategies = {
    record_type: (_flags() if cls is Flag else _fixed(cls))
    for record_type, cls in RECORD_CLASSES.items()
    if cls is not Trim
}
records = st.one_of(*_record_strategies.values(), _unknown_records)

headers = st.builds(
    Header,
    header_flags=st.integers(0, 0xFFFF).map(lambda f: f & ~HeaderFlag.TRIMMED),
    device_id=st.integers(0, 2**64 - 1),
    session_id=st.integers(0, 2**32 - 1),
    activity=st.integers(0, 255),
    hw_rev=st.integers(0, 255),
    fw_version=st.tuples(st.integers(0, 255), st.integers(0, 255), st.integers(0, 255)),
)


def _in_time_order(items: list[Record]) -> list[Record]:
    return sorted(items, key=lambda r: r.t_ms)


# ---------------------------------------------------------------- round trips


@pytest.mark.parametrize("cls", [*RECORD_CLASSES.values(), End], ids=lambda c: c.__name__)
@given(data=st.data())
def test_every_record_type_round_trips(cls: type[FixedRecord], data: st.DataObject) -> None:
    record = data.draw(_flags() if cls is Flag else _fixed(cls))
    payload = record.to_payload()
    assert len(payload) == cls.LAYOUT.size
    assert cls.from_payload(payload) == record


@given(header=headers, items=st.lists(records, max_size=40), duration=st.integers(0, 10_000))
def test_sessions_round_trip(header: Header, items: list[Record], duration: int) -> None:
    items = _in_time_order(items)
    duration_ms = min((items[-1].t_ms if items else 0) + duration, 2**32 - 1)
    data = encode_session(header, items, duration_ms=duration_ms)
    decoded = decode_session(data)
    assert decoded.header == header
    assert list(decoded.records) == items
    assert decoded.complete
    assert decoded.issue is None
    assert decoded.end == End(t_ms=duration_ms, record_count=len(items), file_crc32=zlib.crc32(data[:-20]))


@given(start=st.integers(0, 65535), end=st.integers(0, 65535))
def test_trim_record_round_trips_in_a_trimmed_session(start: int, end: int) -> None:
    trim = Trim(t_ms=0, start_m=start, end_m=end)
    assert decode_session(encode_session(TRIMMED_HEADER, [trim])).records == (trim,)


def test_end_counts_the_records_and_checks_the_file() -> None:
    data = encode_session(HEADER, [TimeSync(0, 1_794_988_320_000)])
    end = decode_session(data).end
    assert end is not None
    assert end.record_count == 1
    assert end.file_crc32 == zlib.crc32(data[:-20])  # END frame: 2 + 16 + 2 bytes


# ---------------------------------------------------------------- the streaming writer


def test_writer_leaves_a_readable_session_after_every_record(header: Header) -> None:
    buffer = io.BytesIO()
    writer = SessionWriter(buffer, header)
    items: list[Record] = [
        TimeSync(0, 1),
        Sample(1000, 1, 2, 3, 4, 5, 6, 7, 3, 9),
        UnknownRecord(0x42, struct.pack("<I", 1500)),
    ]
    for n, record in enumerate(items, start=1):
        writer.append(record)
        decoded = decode_session(buffer.getvalue())
        assert (decoded.records, decoded.complete, decoded.issue) == (tuple(items[:n]), False, "no END record")
    end = writer.finalize(duration_ms=5000)
    assert (writer.record_count, writer.last_t_ms) == (3, 5000)
    decoded = decode_session(buffer.getvalue())
    assert decoded.complete
    assert decoded.end == end


def test_writer_refuses_what_a_reader_would_reject(header: Header) -> None:
    writer = SessionWriter(io.BytesIO(), header)
    writer.append(TimeSync(2000, 1))
    with pytest.raises(EncodeError, match="earlier"):
        writer.append(TimeSync(1999, 1))
    with pytest.raises(EncodeError, match="TRIM"):
        writer.append(Trim(2000, 200, 200))
    with pytest.raises(EncodeError, match="finalize"):
        writer.append_frame(RecordType.END, bytes(16))
    with pytest.raises(EncodeError, match="earlier"):
        writer.finalize(duration_ms=1000)
    writer.finalize()
    with pytest.raises(EncodeError, match="finalized"):
        writer.append(TimeSync(3000, 1))
    with pytest.raises(EncodeError, match="finalized"):
        writer.finalize()


def test_a_trimmed_session_starts_with_trim() -> None:
    with pytest.raises(EncodeError, match="must start with a TRIM"):
        encode_session(TRIMMED_HEADER, [TimeSync(0, 1)])
    with pytest.raises(EncodeError, match="must start with a TRIM"):
        encode_session(TRIMMED_HEADER, [])


def test_session_without_end(header: Header) -> None:
    data = encode_session(header, [TimeSync(0, 1)], end=False)
    decoded = decode_session(data)
    assert (decoded.complete, decoded.end, decoded.issue) == (False, None, "no END record")
    with pytest.raises(EncodeError, match="end=True"):
        encode_session(header, [], end=False, duration_ms=10)


@pytest.mark.parametrize("payload", [b"", bytes(3), bytes(256)])
def test_frames_hold_a_t_ms_and_fit_a_u8_length(payload: bytes) -> None:
    with pytest.raises(EncodeError, match="payload holds"):
        encode_frame(0x42, payload)


# ---------------------------------------------------------------- truncation


def _example(header: Header) -> tuple[bytes, list[Record]]:
    items: list[Record] = [
        TimeSync(0, 1_794_988_320_000),
        *(Sample(1000 * i, 413900000 + i, 21700000, 500, 0, 900, 6500, 8, 3, 12) for i in range(1, 4)),
    ]
    return encode_session(header, items), items


def test_a_session_cut_anywhere_reads_up_to_the_last_whole_record(header: Header) -> None:
    data, items = _example(header)
    for size in range(32, len(data)):
        decoded = decode_session(data[:size])
        assert not decoded.complete
        assert decoded.end is None
        assert decoded.issue is not None
        assert list(decoded.records) == items[: len(decoded.records)]


def test_decoding_stops_at_the_first_bad_crc(header: Header) -> None:
    data, items = _example(header)
    frames = read_frames(data).frames
    corrupt = bytearray(data)
    corrupt[frames[2].offset + 5] ^= 0x01
    decoded = decode_session(bytes(corrupt))
    assert decoded.records == tuple(items[:2])
    assert not decoded.complete
    assert decoded.issue == f"record at byte {frames[2].offset} fails its CRC"


def test_a_cut_inside_the_header_is_a_header_error(header: Header) -> None:
    with pytest.raises(HeaderError):
        decode_session(header.to_bytes()[:31])


# ---------------------------------------------------------------- forward compatibility


def test_unknown_types_are_kept_and_longer_payloads_accepted(header: Header) -> None:
    sample = Sample(2000, 1, 2, 3, 4, 5, 6, 7, 3, 9)
    unknown = UnknownRecord(0x42, struct.pack("<I", 1000) + b"future")
    buffer = io.BytesIO()
    writer = SessionWriter(buffer, header)
    writer.append(unknown)
    writer.append_frame(RecordType.SAMPLE, sample.to_payload() + b"\xde\xad\xbe\xef")
    writer.finalize()
    decoded = decode_session(buffer.getvalue())
    assert decoded.records == (unknown, sample)
    assert decoded.complete
    assert read_frames(buffer.getvalue()).frames[1].payload.endswith(b"\xde\xad\xbe\xef")


# ---------------------------------------------------------------- invalid sessions


def _frame(record_type: int, payload: bytes) -> bytes:
    body = bytes((record_type, len(payload))) + payload
    return body + crc16_ccitt_false(body).to_bytes(2, "little")


def _end(preceding: bytes, record_count: int, t_ms: int = 0) -> bytes:
    payload = struct.pack("<II4xI", t_ms, record_count, zlib.crc32(preceding))
    return _frame(RecordType.END, payload)


def _sample_payload(t_ms: int) -> bytes:
    return Sample(t_ms, 0, 0, 0, 0, 0, 0, 0, 0, 0).to_payload()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (_frame(0x42, bytes(3)), "no t_ms"),
        (_frame(RecordType.SAMPLE, _sample_payload(0)[:20]), "SAMPLE payload is 20 bytes"),
        (
            _frame(RecordType.SAMPLE, _sample_payload(2000)) + _frame(RecordType.SAMPLE, _sample_payload(1000)),
            "earlier",
        ),
        (_frame(RecordType.SAMPLE, _sample_payload(0)) + _frame(RecordType.TRIM, bytes(8)), "TRIM"),
        (_frame(RecordType.END, bytes(15)), "END payload is 15 bytes"),
    ],
)
def test_malformed_records_are_errors(header: Header, body: bytes, message: str) -> None:
    with pytest.raises(RecordError, match=message):
        decode_session(header.to_bytes() + body)


def test_end_must_match_the_session(header: Header) -> None:
    head = header.to_bytes() + _frame(RecordType.SAMPLE, _sample_payload(0))
    with pytest.raises(RecordError, match="END counts 2 records, the session has 1"):
        decode_session(head + _end(head, record_count=2))
    with pytest.raises(RecordError, match="file_crc32"):
        decode_session(head + _end(head[:-1], record_count=1))
    with pytest.raises(RecordError, match="3 bytes follow the END"):
        decode_session(head + _end(head, record_count=1) + b"abc")
    late = header.to_bytes() + _frame(RecordType.SAMPLE, _sample_payload(5000))
    with pytest.raises(RecordError, match="earlier"):
        decode_session(late + _end(late, record_count=1, t_ms=4000))


@given(tail=st.binary(max_size=400))
def test_arbitrary_bytes_after_a_header_never_crash_the_reader(tail: bytes) -> None:
    try:
        decoded = decode_session(HEADER.to_bytes() + tail)
    except ProtocolError:
        return
    assert decoded.complete == (decoded.end is not None)


@given(data=st.binary(max_size=64))
def test_arbitrary_bytes_are_a_header_error(data: bytes) -> None:
    with pytest.raises(HeaderError):
        decode_session(data)
