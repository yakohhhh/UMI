from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from umi_protocol import (
    Fix,
    Flag,
    FlagSource,
    FlagUndo,
    HazardKind,
    Header,
    Lang,
    Record,
    Sample,
    Session,
    TimeSync,
    encode_session,
    haversine_m,
    utc_from_unix_ms,
)
from umi_protocol.constants import GEO_EARTH_RADIUS_M

START_UNIX_MS = 1_794_988_320_000  # 2026-11-18T07:52:00Z

RideBuilder = Callable[[int], list[Sample]]


def _flag(t_ms: int, seq: int) -> Flag:
    return Flag(t_ms, seq, FlagSource.PRESS, HazardKind.NONE, 0, Lang.NONE, 413900000, 21700000, 0, 0, 0)


def test_haversine() -> None:
    assert haversine_m(41.39, 2.17, 41.39, 2.17) == 0.0
    # One degree along a meridian is R·π/180.
    assert haversine_m(41.0, 2.17, 42.0, 2.17) == pytest.approx(GEO_EARTH_RADIUS_M * math.pi / 180)
    # Plaça de Catalunya → Sagrada Família, about 1.9 km as the crow flies.
    assert haversine_m(41.3870, 2.1701, 41.4036, 2.1744) == pytest.approx(1880, abs=20)
    assert haversine_m(0.0, 0.0, 0.0, 180.0) == pytest.approx(math.pi * GEO_EARTH_RADIUS_M)


def test_absolute_time_uses_the_first_time_sync(header: Header) -> None:
    session = Session.from_bytes(
        encode_session(header, [TimeSync(3000, START_UNIX_MS + 3000), TimeSync(60_000, START_UNIX_MS + 99_999)])
    )
    assert session.unix_ms(10_000) == START_UNIX_MS + 10_000
    assert session.started_at == datetime(2026, 11, 18, 7, 52, tzinfo=UTC)
    assert session.utc(1) == datetime(2026, 11, 18, 7, 52, 0, 1000, tzinfo=UTC)


def test_without_time_sync_a_session_cannot_be_placed_in_time(header: Header, straight_ride: RideBuilder) -> None:
    session = Session.from_bytes(encode_session(header, straight_ride(3)))
    assert session.time_sync is None
    assert session.unix_ms(0) is None
    assert session.started_at is None


def test_utc_from_unix_ms_is_exact() -> None:
    assert utc_from_unix_ms(1_794_988_320_123).microsecond == 123_000


def test_path_joins_fixes_and_skips_samples_without_one(header: Header, straight_ride: RideBuilder) -> None:
    samples = straight_ride(11)
    lost = Sample(5500, 0, 0, 0, 0, 900, 6500, 255, Fix.NONE, 2)
    session = Session.from_bytes(encode_session(header, [*samples[:5], lost, *samples[5:]]))
    assert [p.t_ms for p in session.path] == [s.t_ms for s in samples]
    expected = haversine_m(samples[0].lat, samples[0].lon, samples[-1].lat, samples[-1].lon)
    assert session.distance_m == pytest.approx(expected)
    assert session.path[0].distance_m == 0.0


def test_effective_flags_drop_the_undone_ones(header: Header) -> None:
    records: list[Record] = [_flag(1000, 0), _flag(2000, 1), FlagUndo(2300, 1), _flag(3000, 2), FlagUndo(4000, 9)]
    session = Session.from_bytes(encode_session(header, records))
    assert [f.seq for f in session.flags] == [0, 2]
    assert [f.seq for f in session.of_type(Flag)] == [0, 1, 2]


def test_duration(header: Header, straight_ride: RideBuilder) -> None:
    samples = straight_ride(3)
    assert Session.from_bytes(encode_session(header, samples, duration_ms=9000)).duration_ms == 9000
    assert Session.from_bytes(encode_session(header, samples, end=False)).duration_ms == 3000
    assert Session.from_bytes(encode_session(header, [])).duration_ms == 0
