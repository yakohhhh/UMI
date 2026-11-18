#!/usr/bin/env python3
"""Write the hand-made SIL scenarios of the firmware (protocol/sil-scenario.md).

Each scenario is a short ride scripted second by second: a speed profile, road
vibration, the moments something happens (a hard brake, a pothole, button
gestures, keywords). The sensor streams are synthesised from that script with a
fixed seed, so the files are reproducible and reviewable as diffs.

Standard library only:

    python3 firmware/test/scenarios/generate.py
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent

G = 9.80665
IMU_HZ = 100
EARTH_RADIUS_M = 6371008.8
START_UTC = datetime(2026, 11, 18, 7, 52, 0, tzinfo=UTC)
# Carrer de Provença at Passeig de Gràcia, riding south-east along the Cerdà grid.
START_LAT = 41.39520
START_LON = 2.16110
HEADING_DEG = 134.6
# The Clip sits slightly nose-up on the handlebar: gravity leaks into x.
MOUNT_PITCH_DEG = 3.0


@dataclass(frozen=True)
class Shock:
    """A pothole: a decaying vertical oscillation."""

    t_s: float
    amplitude: float = 20.0
    decay_s: float = 0.2
    freq_hz: float = 12.0


@dataclass
class Ride:
    """A ride script. Each speed change (start_s, acceleration m/s², target m/s)
    drives the speed from its start until the next one starts."""

    duration_s: float
    accelerations: list[tuple[float, float, float]]
    shocks: list[Shock] = field(default_factory=list)
    buttons: list[tuple[int, str]] = field(default_factory=list)
    keywords: list[tuple[int, str]] = field(default_factory=list)
    noisy_moments: list[tuple[float, float, float]] = field(default_factory=list)
    seed: int = 42


def nmea(body: str) -> str:
    checksum = 0
    for ch in body:
        checksum ^= ord(ch)
    return f"${body}*{checksum:02X}"


def nmea_coord(value: float, deg_digits: int, pos: str, neg: str) -> tuple[str, str]:
    hemi = pos if value >= 0 else neg
    value = abs(value)
    degrees = int(value)
    minutes = (value - degrees) * 60.0
    return f"{degrees:0{deg_digits}d}{minutes:08.5f}", hemi


def gnss_lines(t_ms: int, lat: float, lon: float, speed: float, heading: float) -> list[str]:
    utc = START_UTC + timedelta(milliseconds=t_ms)
    hms = utc.strftime("%H%M%S") + ".00"
    date = utc.strftime("%d%m%y")
    la, ns = nmea_coord(lat, 2, "N", "S")
    lo, ew = nmea_coord(lon, 3, "E", "W")
    knots = speed / 0.514444
    course = heading if speed > 0.3 else 0.0
    rmc = nmea(f"GNRMC,{hms},A,{la},{ns},{lo},{ew},{knots:.2f},{course:.1f},{date},,,A")
    gga = nmea(f"GNGGA,{hms},{la},{ns},{lo},{ew},1,12,0.8,42.0,M,49.5,M,,")
    return [f"{t_ms},gnss,{rmc}", f"{t_ms},gnss,{gga}"]


def pm_frame(pm1: int, pm25: int, pm10: int) -> str:
    words = [pm1, pm25, pm10, pm1, pm25, pm10] + [0] * 7
    body = bytes([0x42, 0x4D, 0x00, 0x1C]) + b"".join(w.to_bytes(2, "big") for w in words)
    return (body + (sum(body) & 0xFFFF).to_bytes(2, "big")).hex()


def speed_profile(ride: Ride) -> Callable[[float], tuple[float, float]]:
    """Speed and longitudinal acceleration at 100 Hz, integrated once."""
    n = int(ride.duration_s * IMU_HZ) + 1
    speeds, accels = [0.0] * n, [0.0] * n
    v = 0.0
    for i in range(n):
        t = i / IMU_HZ
        a = 0.0
        started = [segment for segment in ride.accelerations if segment[0] <= t]
        if started:
            _, accel, target = started[-1]
            if (accel > 0 and v < target) or (accel < 0 and v > target):
                a = accel
        v = max(0.0, v + a / IMU_HZ)
        speeds[i], accels[i] = v, a

    def at(t: float) -> tuple[float, float]:
        i = min(round(t * IMU_HZ), n - 1)
        return speeds[i], accels[i]

    return at


def render(ride: Ride) -> Iterator[str]:
    rng = random.Random(ride.seed)
    profile = speed_profile(ride)
    pitch = math.radians(MOUNT_PITCH_DEG)
    lat, lon = START_LAT, START_LON
    heading = math.radians(HEADING_DEG)

    yield "# umi-sil-scenario v1"
    yield f"# firmware/test/scenarios/generate.py seed={ride.seed}"
    events: list[tuple[int, int, str]] = []  # (t_ms, order, line) merged in time order
    order = 0

    def emit(t_ms: int, line: str) -> None:
        nonlocal order
        events.append((t_ms, order, line))
        order += 1

    for t_ms in range(0, int(ride.duration_s * 1000) + 1, 10):
        t = t_ms / 1000
        speed, accel = profile(t)
        if t_ms % 1000 == 0:
            if t_ms % 10000 == 0:
                emit(t_ms, f"{t_ms},battery,{3980 - t_ms // 10000},{82 - t_ms // 600000}")
                emit(t_ms, f"{t_ms},env,19.5,61.0")
            if t_ms >= 1000:
                for line in gnss_lines(t_ms, lat, lon, speed, HEADING_DEG):
                    emit(t_ms, line)
            pm25 = 14 + rng.randint(-2, 3)
            emit(t_ms, f"{t_ms},pm,{pm_frame(pm25 - 5, pm25, pm25 + 6)}")
        if t_ms % 100 == 0:
            level = 58.0 + 10.0 * min(speed / 6.0, 1.0) + rng.uniform(-1.5, 1.5)
            for start, end, extra in ride.noisy_moments:
                if start <= t < end:
                    level += extra
            emit(t_ms, f"{t_ms},spl,{level:.1f}")

        # Road texture grows with speed; a standing bike is almost still.
        rough = 0.15 + 0.25 * speed
        vertical = rng.gauss(0.0, rough)
        for shock in ride.shocks:
            dt = t - shock.t_s
            if 0 <= dt < 6 * shock.decay_s:
                vertical += shock.amplitude * math.exp(-dt / shock.decay_s) * math.cos(2 * math.pi * shock.freq_hz * dt)
        ax = accel * math.cos(pitch) + G * math.sin(pitch) + rng.gauss(0.0, 0.3 * rough)
        ay = rng.gauss(0.0, 0.2 * rough)
        az = G * math.cos(pitch) + vertical
        gx, gy, gz = (rng.gauss(0.0, 0.02) for _ in range(3))
        emit(t_ms, f"{t_ms},imu,{ax:.3f},{ay:.3f},{az:.3f},{gx:.3f},{gy:.3f},{gz:.3f}")

        dist = speed / IMU_HZ
        lat += math.degrees(dist * math.cos(heading) / EARTH_RADIUS_M)
        lon += math.degrees(dist * math.sin(heading) / (EARTH_RADIUS_M * math.cos(math.radians(lat))))

    for t_ms, state in ride.buttons:
        emit(t_ms, f"{t_ms},button,{state}")
    for t_ms, result in ride.keywords:
        emit(t_ms, f"{t_ms},keyword,{result}")
    for _, _, line in sorted(events):
        yield line


def press(t_ms: int, hold_ms: int, bounce: bool = False) -> list[tuple[int, str]]:
    """Button edges of one press; with bounce, the contact chatters for a few ms."""
    edges = [(t_ms, "down")]
    if bounce:
        edges += [(t_ms + 3, "up"), (t_ms + 6, "down")]
    edges.append((t_ms + hold_ms, "up"))
    if bounce:
        edges += [(t_ms + hold_ms + 2, "down"), (t_ms + hold_ms + 5, "up")]
    return edges


# Start: stand 2 s, then accelerate to ~18 km/h.
CRUISE = 5.0
START = [(2.0, 1.2, CRUISE)]

SCENARIOS: dict[str, Ride] = {
    # One hard brake (4.5 m/s² for ~0.8 s) the GNSS confirms, then back to cruise.
    "ride-brake": Ride(
        duration_s=40,
        accelerations=[*START, (20.3, -4.5, 1.4), (21.3, 1.0, CRUISE)],
    ),
    # One pothole at cruise speed.
    "ride-pothole": Ride(duration_s=32, accelerations=START, shocks=[Shock(20.0)]),
    # Every button gesture: a bouncy short press, a hold with an understood
    # keyword, a hold with a low-confidence one, a double press that undoes it,
    # and a hold where the rider says nothing.
    "ride-flags": Ride(
        duration_s=52,
        accelerations=START,
        buttons=press(15000, 180, bounce=True)
        + press(22000, 1400)
        + press(30000, 1300)
        + press(38000, 120)
        + press(38300, 120)
        + press(43000, 1100),
        keywords=[(24300, "roadworks,92,ca"), (32000, "pothole,40,es")],
    ),
    # The devkit demo: a bit of everything, and a red light long enough to
    # auto-pause. On the devkit the real BOOT button replaces the scripted one.
    "devkit-demo": Ride(
        duration_s=110,
        accelerations=[*START, (20.3, -4.5, 1.4), (21.3, 1.0, CRUISE), (45.0, -1.5, 0.0), (85.0, 1.2, CRUISE)],
        shocks=[Shock(30.0)],
        buttons=press(25000, 150) + press(35000, 1300) + press(95000, 120) + press(95300, 120),
        keywords=[(37000, "obstacle,88,es")],
        noisy_moments=[(60.0, 66.0, 14.0)],
    ),
}


def main() -> None:
    for name, ride in SCENARIOS.items():
        path = HERE / f"{name}.scn"
        path.write_text("\n".join(render(ride)) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(HERE.parents[2])}")


if __name__ == "__main__":
    main()
