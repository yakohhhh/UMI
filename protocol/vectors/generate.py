#!/usr/bin/env python3
"""Golden session vectors for every UMI codec, built with the reference implementation.

    uv run python protocol/vectors/generate.py           # rewrite the vectors
    uv run python protocol/vectors/generate.py --check   # exit 1 if any byte would change

Deterministic: fixed inputs, positions from integer and IEEE-exact arithmetic, and
RFC 6979 signatures with the TEST-ONLY key in ``test-key.pem``. README.md says what
each file covers.
"""

from __future__ import annotations

import argparse
import io
import itertools
import math
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from umi_protocol import (
    Activity,
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
    Record,
    RecorderState,
    RecordType,
    Sample,
    SessionWriter,
    State,
    Status,
    StatusFlag,
    TimeSync,
    UnknownRecord,
    decode_session,
    encode_session,
    load_private_key_pem,
    public_key_to_pem,
    sign_flag,
    to_json,
    trim_session,
)
from umi_protocol.constants import (
    DETECTION_AUTO_PAUSE_S,
    DETECTION_AUTO_STOP_S,
    RATES_AIR_PERIOD_S,
    RATES_STATUS_PERIOD_S,
)

VECTORS_DIR = Path(__file__).resolve().parent
TEST_KEY = VECTORS_DIR / "test-key.pem"

HEADER = Header(
    header_flags=HeaderFlag.SIMULATED,
    device_id=0x00000000C11B0001,
    session_id=1,
    activity=Activity.RIDE,
    hw_rev=0,
    fw_version=(0, 1, 0),
)
#: 2026-11-18T07:52:00Z, when every vector session starts.
START_UNIX_MS = 1_794_988_320_000

Signer = Callable[[Flag], Flag]


def _signer(key: EllipticCurvePrivateKey) -> Signer:
    return lambda flag: sign_flag(key, HEADER.device_id, HEADER.session_id, flag)


# ---------------------------------------------------------------- minimal, truncated, unknown-record


def minimal_records() -> list[Record]:
    """TIME_SYNC and three 3D-fix samples riding east along Travessera de Gràcia."""
    return [
        TimeSync(t_ms=0, unix_ms=START_UNIX_MS),
        Sample(1000, 414029000, 21564400, 500, 6500, 850, 6420, 9, Fix.THREE_D, 11),
        Sample(2000, 414029200, 21565000, 520, 6500, 1210, 6590, 9, Fix.THREE_D, 12),
        Sample(3000, 414029400, 21565610, 510, 6600, 990, 6475, 8, Fix.THREE_D, 12),
    ]


def minimal() -> bytes:
    return encode_session(HEADER, minimal_records())


def truncated() -> bytes:
    """``minimal`` cut by a power loss: no END, and the last record's CRC is wrong."""
    data = bytearray(encode_session(HEADER, minimal_records(), end=False))
    data[-1] ^= 0xFF
    return bytes(data)


def unknown_record() -> bytes:
    """A record type from the future (0x42) and a SAMPLE grown to 28 bytes."""
    buffer = io.BytesIO()
    writer = SessionWriter(buffer, HEADER)
    records = minimal_records()
    writer.append(records[0])
    writer.append(records[1])
    writer.append(UnknownRecord(0x42, (1500).to_bytes(4, "little") + b"future"))
    writer.append_frame(RecordType.SAMPLE, records[2].to_payload() + bytes.fromhex("deadbeef"))
    writer.finalize()
    return buffer.getvalue()


# ---------------------------------------------------------------- full: every record type


def full_records(sign: Signer) -> list[Record]:
    """Every v1 record type once or more, values chosen to exercise each field."""
    pos = (414038900, 21586100)
    return [
        TimeSync(t_ms=0, unix_ms=START_UNIX_MS),
        State(t_ms=0, state=RecorderState.RECORDING),
        # No fix yet: position and motion are zero, HDOP unknown.
        Sample(1000, 0, 0, 0, 0, 640, 6230, 255, Fix.NONE, 3),
        Sample(2000, *pos, 480, 6420, 910, 6380, 12, Fix.TWO_D, 6),
        Air(t_ms=2000, pm1_dug=52, pm25_dug=87, pm10_dug=131, temp_cc=-150, rh_dpct=712),
        Event(2400, EventKind.HARD_BRAKE, 3850, 6120, 640, *pos),
        # Microphone not ready: noise not available.
        Sample(3000, 414039100, 21586500, 230, 6380, 1130, 0xFFFF, 9, Fix.THREE_D, 9),
        sign(Flag(3200, 0, FlagSource.PRESS, HazardKind.NONE, 0, Lang.NONE, 414039100, 21586500, 230, 1130, 0xFFFF)),
        Event(3600, EventKind.POTHOLE, 4630, 13900, 120, 414039100, 21586500),
        Sample(4000, 414039400, 21587100, 510, 6410, 4630, 6710, 8, Fix.THREE_D, 11),
        sign(Flag(4100, 1, FlagSource.VOICE, HazardKind.ROADWORKS, 92, Lang.CA, 414039400, 21587100, 510, 4630, 6710)),
        Flag(4800, 2, FlagSource.PRESS, HazardKind.NONE, 0, Lang.NONE, 414039400, 21587100, 510, 4630, 6710),
        Sample(5000, 414039700, 21587700, 505, 6400, 1020, 6650, 8, Fix.THREE_D, 11),
        FlagUndo(t_ms=5100, seq=2),
        Status(
            t_ms=5100, battery_pct=18, flags=StatusFlag.LOW_BATTERY, battery_mv=3610, board_temp_cc=3125, free_kib=5120
        ),
        State(t_ms=36000, state=RecorderState.AUTO_PAUSE),
        State(t_ms=41000, state=RecorderState.RESUME),
        Sample(42000, 414040800, 21589000, 150, 6390, 700, 6120, 9, Fix.THREE_D, 12),
    ]


def full(sign: Signer) -> bytes:
    return encode_session(HEADER, full_records(sign))


# ---------------------------------------------------------------- ride: a realistic 3 km trip

#: Travessera de Gràcia → Passeig de Sant Joan → Avinguda Diagonal → Glòries, (lat_e7, lon_e7).
ROUTE = (
    (414029000, 21564400), (414038900, 21586100), (414040800, 21589000), (414044100, 21597100),
    (414047000, 21602100), (414050100, 21609800), (414054200, 21617100), (414050800, 21620600),
    (414048300, 21624700), (414047800, 21624600), (414044600, 21629600), (414042200, 21631900),
    (414023800, 21656300), (414023700, 21657200), (414021300, 21659400), (413991300, 21699600),
    (413999500, 21731900), (414000100, 21736800), (414000700, 21737300), (414003500, 21747800),
    (414005900, 21759100), (414008000, 21765700), (414018900, 21810500), (414021200, 21817700),
    (414022800, 21826300), (414027900, 21845000), (414028700, 21849900), (414030300, 21854100),
    (414030400, 21856200), (414035100, 21875000),
)  # fmt: skip

# Metres per 1e-7 degree at 41.40° N (equirectangular). With products and square
# roots only, the ride's positions are bit-identical on every platform.
_M_PER_E7_LAT = 0.011113295
_M_PER_E7_LON = 0.008349813

_RED_LIGHT_M = 1460  # Passeig de Sant Joan × Diagonal: brake, wait, auto-pause, go
_RED_LIGHT_PAUSED_S = 5  # auto-paused this long before the light turns green
_DIAGONAL_M = 1500


class _Lcg:
    """Tiny deterministic generator (glibc constants), reproducible in any language."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def below(self, n: int) -> int:
        self._state = (self._state * 1103515245 + 12345) & 0x7FFFFFFF
        return (self._state >> 16) % n

    def jitter(self, span: int) -> int:
        return self.below(2 * span + 1) - span


class _Route:
    def __init__(self, points: Sequence[tuple[int, int]]) -> None:
        self._points = points
        self._starts = [0.0]
        self._headings: list[int] = []
        for (lat_a, lon_a), (lat_b, lon_b) in itertools.pairwise(points):
            north = (lat_b - lat_a) * _M_PER_E7_LAT
            east = (lon_b - lon_a) * _M_PER_E7_LON
            self._starts.append(self._starts[-1] + math.sqrt(north * north + east * east))
            self._headings.append(round(math.degrees(math.atan2(east, north)) * 100) % 36000)

    @property
    def length_m(self) -> float:
        return self._starts[-1]

    def at(self, distance_m: float) -> tuple[int, int, int]:
        """``(lat_e7, lon_e7, heading_cdeg)`` after ``distance_m`` along the route."""
        i = next((i for i in range(len(self._headings)) if distance_m < self._starts[i + 1]), len(self._headings) - 1)
        span = self._starts[i + 1] - self._starts[i]
        f = min(1.0, (distance_m - self._starts[i]) / span)
        (lat_a, lon_a), (lat_b, lon_b) = self._points[i], self._points[i + 1]
        return lat_a + round((lat_b - lat_a) * f), lon_a + round((lon_b - lon_a) * f), self._headings[i]


@dataclass(frozen=True, slots=True)
class _Tick:
    """One second of riding: what the SAMPLE of that second says."""

    sample: Sample
    distance_m: float


def _speeds(route: _Route, rng: _Lcg) -> list[int | None]:
    """Speed (cm/s) for every second of the session; ``None`` while auto-paused."""
    speeds: list[int | None] = [180, 320, 450]
    travelled_cm = sum(s or 0 for s in speeds)
    stopped = False
    length_cm = int(route.length_m * 100)
    while travelled_cm < length_cm:
        if not stopped and travelled_cm >= _RED_LIGHT_M * 100:
            speeds += [210, *([0] * DETECTION_AUTO_PAUSE_S), *([None] * _RED_LIGHT_PAUSED_S), 160, 310, 440]
            travelled_cm += 210 + 160 + 310 + 440
            stopped = True
            continue
        speed = min(560 + rng.jitter(45), length_cm - travelled_cm)
        speeds.append(speed)
        travelled_cm += speed
    # Arrived: standing still until the recorder auto-pauses.
    return [*speeds, *([0] * DETECTION_AUTO_PAUSE_S), None]


def _ticks(route: _Route, rng: _Lcg) -> list[_Tick | None]:
    ticks: list[_Tick | None] = []
    travelled_cm = 0
    for second, speed in enumerate(_speeds(route, rng), start=1):
        if speed is None:
            ticks.append(None)
            continue
        travelled_cm += speed
        t_ms = second * 1000
        if second <= 2:  # cold start: no fix for two seconds
            sample = Sample(t_ms, 0, 0, 0, 0, 380 + rng.jitter(60), 6150 + rng.jitter(200), 255, Fix.NONE, 1 + second)
        else:
            lat, lon, heading = route.at(travelled_cm / 100)
            on_diagonal = travelled_cm >= _DIAGONAL_M * 100
            vib = 300 + speed * 7 // 5 + rng.jitter(150) if speed else 35 + rng.jitter(10)
            noise = (6900 if on_diagonal else 6300) + rng.jitter(350)
            hdop, sats = 7 + rng.below(5), 10 + rng.below(5)
            sample = Sample(t_ms, lat, lon, speed, heading, vib, noise, hdop, Fix.THREE_D, sats)
        ticks.append(_Tick(sample, travelled_cm / 100))
    return ticks


def ride_records(sign: Signer) -> tuple[list[Record], int]:
    """About 3 km and 10 minutes from Gràcia to Glòries, with the session's duration."""
    rng = _Lcg(seed=2026)
    route = _Route(ROUTE)
    ticks = _ticks(route, rng)
    moving = [tick for tick in ticks if tick is not None]
    end_of_trip = moving[-1].distance_m
    records: list[Record] = [State(0, RecorderState.RECORDING), TimeSync(3000, START_UNIX_MS + 3000)]

    def first_tick_at(distance_m: float) -> Sample:
        return next(t.sample for t in moving if t.sample.has_fix and t.distance_m >= distance_m)

    def flag(distance_m: float, seq: int, voice: tuple[HazardKind, int, Lang] | None = None) -> Flag:
        s = first_tick_at(distance_m)
        source, (kind, confidence, lang) = (
            (FlagSource.PRESS, (HazardKind.NONE, 0, Lang.NONE)) if voice is None else (FlagSource.VOICE, voice)
        )
        snapshot = (s.lat_e7, s.lon_e7, s.speed_cms, s.vib_mms2, s.noise_cdba)
        return sign(Flag(s.t_ms + 350, seq, source, kind, confidence, lang, *snapshot))

    def pothole(distance_m: float, value: int, peak: int, duration: int) -> Event:
        s = first_tick_at(distance_m)
        return Event(s.t_ms + 300, EventKind.POTHOLE, value, peak, duration, s.lat_e7, s.lon_e7)

    paused = False
    for second, tick in enumerate(ticks, start=1):
        t_ms = second * 1000
        if tick is None:
            if not paused:
                records.append(State(t_ms, RecorderState.AUTO_PAUSE))
            paused = True
            continue
        if paused:
            records.append(State(t_ms, RecorderState.RESUME))
            paused = False
        records.append(tick.sample)
        if second % RATES_AIR_PERIOD_S == 0:
            pm25 = (160 if tick.distance_m >= _DIAGONAL_M else 95) + rng.jitter(25)
            temp, rh = 1420 + second // 60, 690 - second // 60
            records.append(Air(t_ms, pm25 * 65 // 100, pm25, pm25 * 3 // 2 + rng.jitter(10), temp, rh))

    braking = first_tick_at(_RED_LIGHT_M)
    records += [
        Event(braking.t_ms + 400, EventKind.HARD_BRAKE, 3420, 5180, 1250, braking.lat_e7, braking.lon_e7),
        pothole(140, 4150, 12600, 90),  # inside the first 200 m: trimmed away
        pothole(2230, 4710, 14200, 140),
        flag(110, 0),  # trimmed away
        flag(700, 1),
        flag(1900, 2, voice=(HazardKind.ROADWORKS, 92, Lang.CA)),
        flag(2600, 3),
        flag(end_of_trip - 230, 4),
        flag(end_of_trip - 90, 5, voice=(HazardKind.NONE, 41, Lang.ES)),  # keyword not understood; trimmed away
    ]
    undo_3 = next(r for r in records if isinstance(r, Flag) and r.seq == 3).t_ms + 1500
    # Undone after the end of the kept window: the trim must keep this FLAG_UNDO.
    undo_4 = next(r for r in records if isinstance(r, Flag) and r.seq == 4).t_ms + 9000
    records += [FlagUndo(undo_3, 3), FlagUndo(undo_4, 4)]

    arrival_ms = next(t.sample.t_ms for t in moving if t.distance_m >= end_of_trip)
    duration_ms = arrival_ms + DETECTION_AUTO_STOP_S * 1000
    for t_ms in range(RATES_STATUS_PERIOD_S * 1000, duration_ms + 1, RATES_STATUS_PERIOD_S * 1000):
        minutes = t_ms // 60_000
        records.append(
            Status(t_ms, 82 - minutes // 3, StatusFlag(0), 3975 - 4 * minutes, 2350 + 15 * minutes, 6900 - 6 * minutes)
        )
    # The Clip writes records in time order (§1.2); sorted() is stable, so ties keep the order above.
    return sorted(records, key=lambda r: r.t_ms), duration_ms


def ride(sign: Signer) -> bytes:
    records, duration_ms = ride_records(sign)
    return encode_session(HEADER, records, duration_ms=duration_ms)


# ---------------------------------------------------------------- files


def build(key: EllipticCurvePrivateKey) -> dict[str, bytes]:
    """Every vector file, by name."""
    sign = _signer(key)
    sessions = {
        "minimal": minimal(),
        "full": full(sign),
        "truncated": truncated(),
        "unknown-record": unknown_record(),
        "ride": ride(sign),
    }
    trimmed = trim_session(sessions["ride"]).data
    if trimmed is None:
        raise RuntimeError("the ride vector is too short to be uploaded")
    sessions["ride.trimmed"] = trimmed

    files = {"test-key.pub.pem": public_key_to_pem(key.public_key())}
    for name, data in sessions.items():
        files[f"{name}.umis"] = data
        files[f"{name}.json"] = to_json(decode_session(data)).encode()
    return files


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="exit 1 if a committed vector differs")
    args = parser.parse_args(argv)
    files = build(load_private_key_pem(TEST_KEY.read_bytes()))
    if args.check:
        stale = [
            name
            for name, data in files.items()
            if not (VECTORS_DIR / name).is_file() or (VECTORS_DIR / name).read_bytes() != data
        ]
        for name in stale:
            print(f"stale: protocol/vectors/{name}", file=sys.stderr)
        return 1 if stale else 0
    for name, data in files.items():
        (VECTORS_DIR / name).write_bytes(data)
        print(f"wrote protocol/vectors/{name} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
