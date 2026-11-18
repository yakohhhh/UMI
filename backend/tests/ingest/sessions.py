"""Clip sessions synthesised along real street segments, signed like the Clip and trimmed like the phone.

A ride follows the seeded segments' coordinates at a steady speed, one SAMPLE a
second, with AIR, STATUS and TIME_SYNC records as the firmware writes them. Hard
brakes, button presses and noisy or polluted stretches are placed by distance
along the route. Everything is deterministic, keys included.
"""

import hashlib
import itertools
import json
import math
import random
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any

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
    Sample,
    State,
    Status,
    TimeSync,
    encode_session,
    format_device_id,
    private_key_from_raw_hex,
    public_key_to_pem,
    sign_flag,
    trim_session,
)
from umi_protocol.constants import GEO_EARTH_RADIUS_M

STREETS_FILE = Path(__file__).resolve().parents[3] / "src" / "lib" / "mock" / "data" / "streets.json"

# Carrer de Mallorca, Viladomat → Bruc: 1.9 km of straight Cerdà blocks, away from the seeded hazards.
MALLORCA = ("seg-047", "seg-048", "seg-049", "seg-050")

_M_PER_DEG_LAT = math.radians(1) * GEO_EARTH_RADIUS_M
LngLat = tuple[float, float]


@cache
def streets() -> dict[str, dict[str, Any]]:
    """The seeded street segments by id (the network the backend matches against)."""
    return {s["id"]: s for s in json.loads(STREETS_FILE.read_text("utf-8"))}


def route_of(segment_ids: Sequence[str]) -> list[LngLat]:
    """The segments' polylines joined in riding order, each one turned to start where the previous ended."""
    route: list[LngLat] = []
    for segment_id in segment_ids:
        line = [(lon, lat) for lon, lat in streets()[segment_id]["coordinates"]]
        if route and _metres(route[-1], line[-1]) < _metres(route[-1], line[0]):
            line.reverse()
        route.extend(line[1:] if route and _metres(route[-1], line[0]) < 1 else line)
    return route


@dataclass(frozen=True)
class SoftwareClip:
    """A Clip with a software key, as the simulator provisions them (deterministic here)."""

    device_id: int
    serial: str
    private_key: EllipticCurvePrivateKey

    @classmethod
    def numbered(cls, n: int) -> "SoftwareClip":
        digest = hashlib.sha256(f"umi-test-clip-{n}".encode()).hexdigest()
        return cls(int(digest[:16], 16), f"UMI-TEST-{n:04d}", private_key_from_raw_hex(digest))

    @property
    def device_hex(self) -> str:
        return format_device_id(self.device_id)

    def registration(self, athlete_id: str, *, simulated: bool = True) -> dict[str, Any]:
        """The body of POST /v1/dev/devices."""
        return {
            "deviceId": self.device_hex,
            "serial": self.serial,
            "publicKeyPem": public_key_to_pem(self.private_key.public_key()).decode("ascii"),
            "hwRev": 0,
            "firmware": "0.9.0",
            "simulated": simulated,
            "athlete": {"id": athlete_id, "name": f"Test {athlete_id.title()}", "vehicle": "e-bike"},
        }


class Signature(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    # Signed by another Clip's key.
    FORGED = "forged"


@dataclass(frozen=True)
class Press:
    """The flag button, `at_m` metres along the route."""

    at_m: float
    kind: HazardKind = HazardKind.NONE
    # Voice keyword confidence; a press without a keyword has none.
    confidence: int = 0
    undone: bool = False
    signature: Signature = Signature.VALID

    @property
    def source(self) -> FlagSource:
        return FlagSource.VOICE if self.kind is not HazardKind.NONE else FlagSource.PRESS


@dataclass(frozen=True)
class Brake:
    at_m: float
    decel_mps2: float = 4.0


@dataclass(frozen=True)
class Stretch:
    """From `from_m` to `to_m` along the route."""

    from_m: float
    to_m: float

    def __contains__(self, d: float) -> bool:
        return self.from_m <= d <= self.to_m


@dataclass(frozen=True)
class RideSpec:
    start: datetime
    segments: Sequence[str] = MALLORCA
    speed_kmh: float = 18.0
    activity: Activity = Activity.RIDE
    presses: Sequence[Press] = ()
    brakes: Sequence[Brake] = ()
    vib_mps2: float = 0.9
    noise_dba: float = 64.0
    pm25: float = 12.0
    loud: Sequence[Stretch] = ()
    smoky: Sequence[Stretch] = ()
    # Standard deviation of the position error, metres.
    gnss_noise_m: float = 0.0
    # Moves the whole ride by (lon, lat) degrees, e.g. out of Barcelona.
    shift_deg: tuple[float, float] = (0.0, 0.0)
    simulated: bool = True
    time_sync: bool = True
    seed: int = 0


def record(spec: RideSpec, clip: SoftwareClip, session_id: int) -> bytes:
    """The session as the Clip writes it, before the phone trims it."""
    route = route_of(spec.segments)
    cumulative = [0.0, *itertools.accumulate(_metres(a, b) for a, b in itertools.pairwise(route))]
    speed = spec.speed_kmh / 3.6
    seconds = math.floor(cumulative[-1] / speed)
    rng = random.Random(spec.seed)

    def at(d: float) -> tuple[LngLat, float]:
        """Position and heading `d` metres along the route."""
        i = min(max(0, bisect_right(cumulative, d) - 1), len(route) - 2)
        a, b = route[i], route[i + 1]
        f = (d - cumulative[i]) / (cumulative[i + 1] - cumulative[i])
        lon, lat = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
        return (lon + spec.shift_deg[0], lat + spec.shift_deg[1]), _bearing(a, b)

    def t_at(d: float) -> int:
        return round(d / speed * 1000)

    records: list[Record] = [State(0, RecorderState.RECORDING)]
    if spec.time_sync:
        records.append(TimeSync(0, round(spec.start.timestamp() * 1000)))
    for second in range(seconds + 1):
        d = second * speed
        (lon, lat), heading = at(d)
        lon, lat = _jitter(lon, lat, spec.gnss_noise_m, rng)
        noise = 84.0 if any(d in s for s in spec.loud) else spec.noise_dba
        records.append(
            Sample(
                t_ms=second * 1000,
                lat_e7=round(lat * 1e7),
                lon_e7=round(lon * 1e7),
                speed_cms=round(speed * 100),
                heading_cdeg=round(heading * 100) % 36000,
                vib_mms2=round(spec.vib_mps2 * 1000),
                noise_cdba=round(noise * 100),
                hdop_d=8,
                fix=Fix.THREE_D,
                sats=12,
            )
        )
        if second % 10 == 0:
            pm25 = 40.0 if any(d in s for s in spec.smoky) else spec.pm25
            records.append(Air(second * 1000, round(pm25 * 7), round(pm25 * 10), round(pm25 * 14), 1950, 600))
        if second % 60 == 0:
            records.append(Status(second * 1000, 80 - second // 600, 0, 3900, 2500, 1000))
    for brake in spec.brakes:
        (lon, lat), _ = at(brake.at_m)
        value = round(brake.decel_mps2 * 1000)
        records.append(
            Event(t_at(brake.at_m) + 300, EventKind.HARD_BRAKE, value, round(value * 1.5), 600, *_e7(lon, lat))
        )
    for seq, press in enumerate(spec.presses):
        t_ms = t_at(press.at_m) + 500
        position, _ = at(press.at_m)
        records.append(_flag(press, seq=seq, t_ms=t_ms, at=position, speed=speed, clip=clip, session_id=session_id))
        if press.undone:
            records.append(FlagUndo(t_ms + 800, seq))
    records.sort(key=lambda r: r.t_ms)
    header = Header(
        header_flags=HeaderFlag.SIMULATED if spec.simulated else 0,
        device_id=clip.device_id,
        session_id=session_id,
        activity=spec.activity,
        fw_version=(0, 9, 0),
    )
    return encode_session(header, records)


def trimmed(spec: RideSpec, clip: SoftwareClip, session_id: int) -> bytes:
    """The session as the phone uploads it."""
    result = trim_session(record(spec, clip, session_id))
    assert result.data is not None, result.reason
    return result.data


def _flag(press: Press, *, seq: int, t_ms: int, at: LngLat, speed: float, clip: SoftwareClip, session_id: int) -> Flag:
    flag = Flag(
        t_ms=t_ms,
        seq=seq,
        source=press.source,
        kind=press.kind,
        confidence=press.confidence,
        lang=Lang.CA if press.source is FlagSource.VOICE else Lang.NONE,
        lat_e7=round(at[1] * 1e7),
        lon_e7=round(at[0] * 1e7),
        speed_cms=round(speed * 100),
        vib_mms2=900,
        noise_cdba=6400,
    )
    match press.signature:
        case Signature.VALID:
            return sign_flag(clip.private_key, clip.device_id, session_id, flag)
        case Signature.FORGED:
            return sign_flag(SoftwareClip.numbered(-1).private_key, clip.device_id, session_id, flag)
        case Signature.MISSING:
            return flag


def _e7(lon: float, lat: float) -> tuple[int, int]:
    return round(lat * 1e7), round(lon * 1e7)


def _metres(a: LngLat, b: LngLat) -> float:
    dx = (b[0] - a[0]) * _M_PER_DEG_LAT * math.cos(math.radians(a[1]))
    return math.hypot(dx, (b[1] - a[1]) * _M_PER_DEG_LAT)


def _bearing(a: LngLat, b: LngLat) -> float:
    dx = (b[0] - a[0]) * math.cos(math.radians(a[1]))
    return math.degrees(math.atan2(dx, b[1] - a[1])) % 360


def _jitter(lon: float, lat: float, sigma_m: float, rng: random.Random) -> LngLat:
    if not sigma_m:
        return lon, lat
    d_lat = rng.gauss(0, sigma_m) / _M_PER_DEG_LAT
    d_lon = rng.gauss(0, sigma_m) / (_M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return lon + d_lon, lat + d_lat
