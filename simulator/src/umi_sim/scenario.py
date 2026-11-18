"""Export a simulated ride as a firmware SIL scenario (``protocol/sil-scenario.md``).

A scenario is the layer below ``.umis``: what the sensors output, line by line,
so the real firmware logic (detectors, button state machine, signing, the
session writer) can run on it (``pio run -e sil``). It is built from the same
ride as the simulator's own ``.umis``: the 100 Hz IMU carries the ride's
accelerations, turns, road vibration, impacts and hard brakes; NMEA, PM frames,
sound levels, environment and battery are the readings ``sensors.py`` made; the
button lines replay the rider's gestures, with contact bounce now and then.

Time is milliseconds since power-on, which is ``LEAD_IN_S`` before the rider
moves off.
"""

from __future__ import annotations

import heapq
import math
import random
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TextIO

from umi_protocol.constants import BUTTON_DEBOUNCE_MS, BUTTON_DOUBLE_PRESS_GAP_MS, BUTTON_HOLD_MS, RATES_IMU_HZ

from .frames import gngga, gnrmc, pms_frame
from .geo import Polyline, turn_deg
from .hazards import Gesture, GestureKind
from .rider import Vehicle
from .sensors import Brake, Impact, Readings
from .simulation import SimulatedRide

HEADER = "# umi-sil-scenario v1"
GRAVITY_MPS2 = 9.80665

_IMU_PERIOD_MS = 1000 // RATES_IMU_HZ
# The turn rate is the change of heading over this distance; riders round a
# corner over a few metres on each side of it.
_YAW_BASE_M = 2.0
_CORNER_M = 6.0
_BOUNCE_P = 0.3
_RUNNER_CADENCE_HZ = (2.6, 3.0)
# Rank among lines sharing a t_ms. A GNSS epoch is RMC then GGA (sil-scenario.md).
_RANK = {"battery": 0, "env": 1, "imu": 2, "rmc": 3, "gga": 4, "pm": 5, "spl": 6, "button": 7, "keyword": 8}

type _Line = tuple[int, int, str]


@dataclass(frozen=True, slots=True)
class ScenarioInfo:
    lines: int
    duration_ms: int


def write_scenario(ride: SimulatedRide, out: TextIO, *, title: str) -> ScenarioInfo:
    """Write the scenario; ``title`` goes into the second comment line (who, where, which seed)."""
    out.write(f"{HEADER}\n# {title}\n")
    lines = last = 0
    for t_ms, _, text in _lines(ride):
        out.write(f"{t_ms},{text}\n")
        lines += 1
        last = t_ms
    return ScenarioInfo(lines, last)


def _lines(ride: SimulatedRide) -> Iterator[_Line]:
    rng = random.Random(f"umi-sim/{ride.spec.seed}/scenario")
    r = ride.readings
    streams = [
        _imu(ride, random.Random(rng.getrandbits(64))),
        _gnss(ride),
        _pm(r),
        _spl(r),
        _env(r),
        _battery(r),
        _button(ride, random.Random(rng.getrandbits(64))),
    ]
    return heapq.merge(*streams)


def _ms(readings: Readings, t: float) -> int:
    """Scenario time of ride time ``t``: power-on is the first reading."""
    return round((t - readings.t0) * 1000)


def _line(t_ms: int, kind: str, fields: str, *, rank: str | None = None) -> _Line:
    return t_ms, _RANK[rank or kind], f"{kind},{fields}"


def _gnss(ride: SimulatedRide) -> Iterator[_Line]:
    for epoch in ride.readings.gnss:
        at = ride.utc(epoch.t)
        t_ms = _ms(ride.readings, epoch.t)
        yield _line(t_ms, "gnss", gnrmc(epoch, at), rank="rmc")
        yield _line(t_ms, "gnss", gngga(epoch, at), rank="gga")


def _pm(r: Readings) -> Iterator[_Line]:
    for i, frame in enumerate(r.pm):
        yield _line(_ms(r, r.t0 + i), "pm", pms_frame(frame).hex())


def _spl(r: Readings) -> Iterator[_Line]:
    # noise_10hz[i] covers the second before reading i; the first one predates power-on.
    for i in range(1, len(r.noise_10hz)):
        start = _ms(r, r.t0 + i - 1)
        for k, level in enumerate(r.noise_10hz[i]):
            yield _line(start + 100 * k, "spl", f"{level:.1f}")


def _env(r: Readings) -> Iterator[_Line]:
    for env in r.env:
        yield _line(_ms(r, env.t), "env", f"{env.temp_c:.2f},{env.rh_pct:.1f}")


def _battery(r: Readings) -> Iterator[_Line]:
    for battery in r.battery:
        yield _line(_ms(r, battery.t), "battery", f"{battery.mv},{round(battery.pct)}")


# ---------------------------------------------------------------- IMU


def _imu(ride: SimulatedRide, rng: random.Random) -> Iterator[_Line]:
    """100 Hz accelerometer (m/s², gravity included) and gyroscope (rad/s); x forward, y left, z up."""
    r = ride.readings
    line = ride.route.line
    runner = ride.spec.vehicle is Vehicle.RUN
    cadence = rng.uniform(*_RUNNER_CADENCE_HZ)
    impacts = list(r.impacts)
    brakes = list(r.brakes)
    background = _background_vib(r)
    end_ms = _ms(r, r.end)
    for t_ms in range(0, end_ms + 1, _IMU_PERIOD_MS):
        t = r.t0 + t_ms / 1000
        state = ride.trajectory.state_at(t)
        level = background[r.index(t)]
        yaw = _yaw_rate(line, state.s, state.v) if state.v > 0.05 else 0.0
        if runner and state.v > 0.3:
            phase = 2 * math.pi * cadence * t
            # A stride is a vertical bounce and a push-and-brake along x, twice per cycle of cadence.
            vertical = level * math.sqrt(2) * math.sin(phase)
            forward = state.a + 1.5 * math.sin(phase + 0.6)
        else:
            vertical = rng.gauss(0.0, level) + sum(i.accel(t - i.t) for i in _active(impacts, t))
            forward = state.a - _brake_peak(brakes, t) + rng.gauss(0.0, 0.25 * level)
        ax = forward
        ay = state.v * yaw + rng.gauss(0.0, 0.15 * level)
        az = GRAVITY_MPS2 + vertical
        gx, gy = rng.gauss(0.0, 0.002 + 0.01 * level), rng.gauss(0.0, 0.002 + 0.01 * level)
        gz = yaw + rng.gauss(0.0, 0.002)
        yield _line(t_ms, "imu", f"{ax:.3f},{ay:.3f},{az:.3f},{gx:.4f},{gy:.4f},{gz:.4f}")


def _yaw_rate(line: Polyline, s: float, v: float) -> float:
    """Turn rate at ``s`` riding at ``v`` (rad/s), counter-clockwise positive like a z-up gyro."""
    ahead = min(s + _YAW_BASE_M, line.length)
    behind = max(ahead - _YAW_BASE_M, 0.0)
    clockwise = turn_deg(line.bearing_at(behind, _CORNER_M), line.bearing_at(ahead, _CORNER_M))
    return -math.radians(clockwise) / (ahead - behind) * v


def _background_vib(r: Readings) -> list[float]:
    """Per-second RMS without the impacts (the impact waveforms are added sample by sample)."""
    energy = [v * v for v in r.vib]
    for impact in r.impacts:
        i = r.index(impact.t)
        energy[i] = max(energy[i] - impact.amplitude**2 * impact.ring_s / 4, 0.0)
    return [math.sqrt(e) for e in energy]


def _active(impacts: list[Impact], t: float) -> Iterator[Impact]:
    """Impacts still ringing at ``t``; those long gone are dropped from the front of the list."""
    while impacts and t - impacts[0].t > 2 * impacts[0].duration_s:
        impacts.pop(0)
    for impact in impacts:
        if impact.t > t:
            break
        yield impact


def _brake_peak(brakes: list[Brake], t: float) -> float:
    """The extra deceleration that takes a hard brake from its mean to its peak, mid-brake.

    A raised cosine over the middle 40 % of the brake: the edges keep the mean
    (above the threshold), the middle reaches the peak.
    """
    while brakes and t > brakes[0].t + brakes[0].duration:
        brakes.pop(0)
    if not brakes or t < brakes[0].t:
        return 0.0
    brake = brakes[0]
    u = (t - brake.t) / brake.duration
    if not 0.3 <= u <= 0.7:
        return 0.0
    return (brake.peak - brake.mean) * 0.5 * (1 - math.cos(2 * math.pi * (u - 0.3) / 0.4))


# ---------------------------------------------------------------- button


def _button(ride: SimulatedRide, rng: random.Random) -> Iterator[_Line]:
    r = ride.readings
    lines: list[_Line] = []
    for gesture in ride.gestures:
        down = _ms(r, gesture.t)
        for t_ms, pressed in _edges(gesture, down, rng):
            lines.extend(_bounced(t_ms, pressed, rng))
        if gesture.kind is GestureKind.HOLD and (heard := r.keywords.get(gesture)) is not None:
            spoken = down + BUTTON_HOLD_MS + rng.randint(800, 2500)
            fields = f"{heard.kind.name.lower()},{heard.confidence},{heard.lang.name.lower()}"
            lines.append(_line(spoken, "keyword", fields))
    return iter(sorted(lines))


def _edges(gesture: Gesture, down: int, rng: random.Random) -> list[tuple[int, bool]]:
    """Clean contact edges of one gesture (bounce is added afterwards)."""
    if gesture.kind is GestureKind.PRESS:
        return [(down, True), (down + rng.randint(80, 250), False)]
    if gesture.kind is GestureKind.HOLD:
        return [(down, True), (down + BUTTON_HOLD_MS + rng.randint(100, 500), False)]
    first_up = down + rng.randint(60, 120)
    second_down = first_up + rng.randint(80, BUTTON_DOUBLE_PRESS_GAP_MS - 150)
    return [(down, True), (first_up, False), (second_down, True), (second_down + rng.randint(60, 120), False)]


def _bounced(t_ms: int, pressed: bool, rng: random.Random) -> list[_Line]:
    """An edge, sometimes followed by a few contact bounces, all settled well inside the debounce time."""
    state = "down" if pressed else "up"
    other = "up" if pressed else "down"
    lines = [_line(t_ms, "button", state)]
    if rng.random() < _BOUNCE_P:
        t = t_ms
        for _ in range(rng.randint(1, 3)):
            t += rng.randint(1, BUTTON_DEBOUNCE_MS // 6)
            lines.append(_line(t, "button", other))
            t += rng.randint(1, BUTTON_DEBOUNCE_MS // 6)
            lines.append(_line(t, "button", state))
    return lines
