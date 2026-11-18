"""What the Clip's sensors would read along a simulated ride.

One reading per whole second (GNSS epoch, vertical vibration RMS, sound level,
one Plantower PM frame), the environment and the battery every 10 s, and the
discrete things that happen: impacts (potholes and bumps), hard brakes, and what
the keyword recogniser heard for each hold. ``clip.py`` turns these into records
the way the firmware does; ``scenario.py`` expands them into raw sensor streams.

Levels come from the street being ridden at that local hour: PM2.5 and dB(A)
through the inverse score conversions of ``src/lib/score.ts``, vibration from
the segment's surface RMS. Street levels stay in the product's ranges (PM2.5
5–35 µg/m³, noise 50–80 dB(A)); brief traffic noise events such as a horn or a
motorbike go above them, as they do in the street.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from itertools import pairwise

from umi_protocol import HazardKind, Lang
from umi_protocol.constants import (
    AIR_HUMIDITY_CAP_PCT,
    AIR_PM25_HUMIDITY_KAPPA,
    DETECTION_AUTO_STOP_S,
    DETECTION_HARD_BRAKE_MPS2,
)

from .geo import to_lonlat
from .hazards import Gesture, GestureKind
from .network import Route
from .rider import MotionState, Trajectory, Vehicle
from .scores import db_from_noise_score, pm_from_air_score
from .world import Pothole, Severity, Street, StreetKind, World

type HourAt = Callable[[float], float]
"""Local hour of day (fractional) at a ride time."""

#: The Clip wakes this long before the rider moves off (seconds).
LEAD_IN_S = 5
#: Readings continue this long after arrival: enough for the Clip to auto-stop.
TAIL_S = DETECTION_AUTO_STOP_S + 15
ENV_PERIOD_S = 10

PM25_RANGE = (5.0, 35.0)
NOISE_RANGE = (50.0, 80.0)

# GNSS: user range error times HDOP gives the position error, which wanders
# slowly (Gauss-Markov) as it does on a real receiver.
_UERE_M = 2.0
_GNSS_ERROR_TAU_S = 25.0
_TTFF_S = (3.0, 20.0)
_OUTAGE_P = 0.1
_HDOP: dict[StreetKind, float] = {
    "arterial": 0.8,
    "boulevard": 0.7,
    "street": 1.0,
    "green": 0.9,
    "promenade": 1.1,
    "seafront": 0.7,
}
# Narrow old streets hide the sky.
_CANYON_DISTRICTS = frozenset({"Gràcia", "Ciutat Vella"})

# Vertical vibration grows with speed; a segment's surface RMS is taken at 18 km/h.
# Small wheels without suspension shake more.
_VIB_REF_SPEED_MS = 5.0
_VIB_FACTOR = {Vehicle.E_BIKE: 0.95, Vehicle.BIKE: 1.0, Vehicle.SCOOTER: 1.35}
# Standing still: the sensor's own noise and a hand on the handlebar.
_IDLE_VIB_MPS2 = 0.04
# Mapped potholes lie on the street's centreline; riders swerve around some of them.
_POTHOLE_REACH_M = 4.0
_POTHOLE_HIT_P: dict[Severity, float] = {"high": 0.55, "medium": 0.4, "low": 0.3}
_POTHOLE_PEAK_MPS2: dict[Severity, tuple[float, float]] = {
    "high": (24.0, 40.0),
    "medium": (18.0, 32.0),
    "low": (14.0, 26.0),
}
_IMPACT_FACTOR = {Vehicle.E_BIKE: 0.9, Vehicle.BIKE: 1.0, Vehicle.SCOOTER: 1.3}
# Manhole covers, kerb ramps, patches: per km, per m/s² of surface RMS above smooth asphalt.
_BUMPS_PER_KM = 3.0
_SMOOTH_VIB_MPS2 = 0.8

_NOISE_TAU_S = 6.0
_NOISE_SIGMA_DB = 1.8
# Chance per second that a horn, a motorbike or a bus pulls away next to the rider.
_NOISE_EVENT_P: dict[StreetKind, float] = {
    "arterial": 1 / 80,
    "boulevard": 1 / 100,
    "street": 1 / 150,
    "green": 1 / 300,
    "promenade": 1 / 200,
    "seafront": 1 / 300,
}

_PM_MIX_TAU_S = 15.0
_PM_DRIFT_TAU_S = 30.0
_PM_DRIFT = 0.06
_PM_SPIKE_P = 1 / 400
_PM_SPIKE_TAU_S = 12.0
_PM_SENSOR_NOISE = 0.03

# Approximate monthly normals for Barcelona: mean temperature (°C), mean relative humidity (%).
_CLIMATE = (
    (10.0, 69.0), (10.9, 67.0), (12.8, 67.0), (14.8, 67.0), (18.1, 68.0), (22.0, 66.0),
    (24.9, 66.0), (25.4, 68.0), (22.6, 70.0), (18.8, 71.0), (14.1, 70.0), (11.2, 69.0),
)  # fmt: skip

# Li-ion open-circuit voltage (mV) against charge (%), and the drain while awake.
_OCV = ((0, 3300), (5, 3500), (10, 3600), (20, 3680), (40, 3760), (60, 3850), (80, 3980), (100, 4180))
_LOAD_DROP_MV = 40
DRAIN_PCT_PER_H = 12.0


@dataclass(frozen=True, slots=True)
class GnssEpoch:
    """What the receiver reports at one whole UTC second (ride time ``t``)."""

    t: int
    fixed: bool
    lat: float
    lon: float
    speed: float
    course: float
    hdop: float | None
    sats: int
    altitude: float


@dataclass(frozen=True, slots=True)
class PmFrame:
    """One Plantower reading: atmospheric PM1, PM2.5 and PM10 in whole µg/m³, before any correction."""

    pm1: int
    pm25: int
    pm10: int


@dataclass(frozen=True, slots=True)
class Env:
    t: int
    temp_c: float
    rh_pct: float


@dataclass(frozen=True, slots=True)
class Battery:
    t: int
    pct: float
    mv: int


@dataclass(frozen=True, slots=True)
class Impact:
    """A shock on the vertical axis: a damped oscillation peaking at ``peak`` m/s².

    ``rms`` is the vertical RMS of the second it falls in, impact included: what
    the Clip's 1 s window sees.
    """

    t: float
    peak: float
    ring_s: float
    freq_hz: float
    rms: float

    @property
    def amplitude(self) -> float:
        return self.peak / _shape_peak(self.ring_s, self.freq_hz)

    @property
    def duration_s(self) -> float:
        """Until the oscillation has decayed to 5 % of its amplitude."""
        return 3 * self.ring_s

    def accel(self, dt: float) -> float:
        """Vertical acceleration (gravity removed) ``dt`` seconds after the onset."""
        if dt < 0.0:
            return 0.0
        return self.amplitude * math.exp(-dt / self.ring_s) * math.sin(2 * math.pi * self.freq_hz * dt)


@dataclass(frozen=True, slots=True)
class Brake:
    """Deceleration above the hard-brake threshold: start, duration, mean and peak (m/s²)."""

    t: float
    duration: float
    mean: float
    peak: float


@dataclass(frozen=True, slots=True)
class KeywordResult:
    """What the on-Clip recogniser returned for a hold window."""

    kind: HazardKind
    confidence: int
    lang: Lang


@dataclass(frozen=True)
class Readings:
    """Everything the sensors produced; per-second tuples start at ride time ``t0``."""

    t0: int
    gnss: tuple[GnssEpoch, ...]
    vib: tuple[float, ...]
    noise: tuple[float, ...]
    noise_10hz: tuple[tuple[float, ...], ...]
    pm: tuple[PmFrame, ...]
    env: tuple[Env, ...]
    battery: tuple[Battery, ...]
    impacts: tuple[Impact, ...]
    brakes: tuple[Brake, ...]
    keywords: Mapping[Gesture, KeywordResult | None]

    @property
    def end(self) -> int:
        """Ride time of the last reading."""
        return self.t0 + len(self.gnss) - 1

    def index(self, t: float) -> int:
        """Index of the second that holds ride time ``t`` (clamped to the readings)."""
        return min(max(math.ceil(t) - self.t0, 0), len(self.gnss) - 1)

    def env_at(self, t: float) -> Env:
        return self.env[min(max(int((t - self.t0) // ENV_PERIOD_S), 0), len(self.env) - 1)]

    def battery_at(self, t: float) -> Battery:
        return self.battery[min(max(int((t - self.t0) // ENV_PERIOD_S), 0), len(self.battery) - 1)]


@dataclass(frozen=True, slots=True)
class Weather:
    """The day's mean temperature and humidity; the same for every rider that day."""

    temp_c: float
    rh_pct: float

    @classmethod
    def on(cls, day: date) -> Weather:
        rng = random.Random(f"umi-sim/weather/{day.isoformat()}")
        temp, rh = _CLIMATE[day.month - 1]
        return cls(temp + rng.gauss(0.0, 1.8), rh + rng.gauss(0.0, 6.0))

    def at(self, hour: float) -> tuple[float, float]:
        """Temperature (°C) and relative humidity (%) at a local hour: warmest and driest mid-afternoon."""
        phase = math.cos(2 * math.pi * (hour - 15.0) / 24.0)
        return self.temp_c + 3.5 * phase, min(max(self.rh_pct - 9.0 * phase, 25.0), 95.0)


def humidity_growth(rh_pct: float) -> float:
    """How much humidity inflates a laser PM2.5 reading; the Clip divides by it (``[air]``)."""
    rh = min(max(rh_pct, 0.0), AIR_HUMIDITY_CAP_PCT) / 100.0
    return 1.0 + AIR_PM25_HUMIDITY_KAPPA * rh / (1.0 - rh)


def street_pm25(street: Street, hour: int) -> float:
    """PM2.5 (µg/m³) the street's air score implies at ``hour``."""
    return _clamp(pm_from_air_score(street.scores_at(hour).air), *PM25_RANGE)


def street_noise(street: Street, hour: int) -> float:
    """Sound level (dB(A)) the street's noise score implies at ``hour``."""
    return _clamp(db_from_noise_score(street.scores_at(hour).noise), *NOISE_RANGE)


def battery_mv(pct: float) -> int:
    """Cell voltage under load at ``pct`` charge."""
    for (p0, v0), (p1, v1) in pairwise(_OCV):
        if pct <= p1:
            return round(v0 + (v1 - v0) * (max(pct, p0) - p0) / (p1 - p0)) - _LOAD_DROP_MV
    return _OCV[-1][1] - _LOAD_DROP_MV


def measure(
    route: Route,
    trajectory: Trajectory,
    gestures: Sequence[Gesture],
    world: World,
    *,
    vehicle: Vehicle,
    depart_local: datetime,
    weather: Weather,
    battery_pct: float,
    lang: Lang,
    rng: random.Random,
) -> Readings:
    """Sensor readings for a ride that leaves at ``depart_local`` (a whole second, local time)."""
    t0 = -LEAD_IN_S
    times = range(t0, math.ceil(trajectory.arrival) + TAIL_S + 1)
    start_hour = depart_local.hour + depart_local.minute / 60 + depart_local.second / 3600

    def hour_at(t: float) -> float:
        return (start_hour + t / 3600) % 24

    states = [trajectory.state_at(t) for t in times]
    streets = [route.street_at(state.s) for state in states]
    gnss = _gnss(route, trajectory.arrival, times=times, states=states, streets=streets, rng=rng)
    base_vib = [_riding_vib(street, state.v, vehicle, rng) for street, state in zip(streets, states, strict=True)]
    vib, impacts = _with_impacts(base_vib, _impacts(route, trajectory, world, vehicle, rng), t0)
    noise, noise_10hz = _noise(times, streets, hour_at, rng)
    pm = _pm(times, streets, hour_at, weather, rng)
    env = tuple(Env(t, *_jitter_env(weather.at(hour_at(t)), rng)) for t in times[::ENV_PERIOD_S])
    battery = tuple(_battery(t, battery_pct - DRAIN_PCT_PER_H * (t - t0) / 3600) for t in times[::ENV_PERIOD_S])
    brakes = tuple(
        Brake(d.t, d.duration, d.mean, d.mean * rng.uniform(1.1, 1.4))
        for d in trajectory.decelerations(above=DETECTION_HARD_BRAKE_MPS2)
    )
    keywords = {
        g: _hear(g, trajectory.state_at(g.t + 1.5).v * 3.6, lang, rng) for g in gestures if g.kind is GestureKind.HOLD
    }
    return Readings(t0, gnss, vib, noise, noise_10hz, pm, env, battery, impacts, brakes, keywords)


# ---------------------------------------------------------------- GNSS


def _gnss(
    route: Route,
    arrival: float,
    *,
    times: range,
    states: Sequence[MotionState],
    streets: Sequence[Street],
    rng: random.Random,
) -> tuple[GnssEpoch, ...]:
    first_fix = times[0] + rng.uniform(*_TTFF_S)
    outage = (-1.0, -1.0)
    if rng.random() < _OUTAGE_P:
        start = rng.uniform(0.3, 0.7) * arrival
        outage = (start, start + rng.uniform(3.0, 10.0))
    decay = math.exp(-1.0 / _GNSS_ERROR_TAU_S)
    kick = math.sqrt(1.0 - decay * decay)
    ex = ey = hdop_drift = 0.0
    course = 0.0
    epochs = []
    for t, state, street in zip(times, states, streets, strict=True):
        hdop_drift = hdop_drift * 0.95 + rng.gauss(0.0, 0.03)
        hdop = _clamp(_HDOP[street.kind] + (0.4 if street.district in _CANYON_DISTRICTS else 0.0) + hdop_drift, 0.5, 5)
        sigma = _UERE_M * hdop
        ex = ex * decay + kick * rng.gauss(0.0, sigma)
        ey = ey * decay + kick * rng.gauss(0.0, sigma)
        if t < first_fix or outage[0] <= t <= outage[1]:
            epochs.append(GnssEpoch(t, False, 0.0, 0.0, 0.0, 0.0, None, rng.randint(0, 3), 0.0))
            continue
        x, y = route.line.point_at(state.s)
        lon, lat = to_lonlat((x + ex, y + ey))
        speed = abs(rng.gauss(0.0, 0.04)) if state.v < 0.1 else max(state.v + rng.gauss(0.0, 0.07), 0.0)
        if state.v > 0.8:  # course over ground is noise when standing still: receivers hold the last one
            course = (route.line.bearing_at(state.s, smooth_m=6.0) + rng.gauss(0.0, 1.5)) % 360.0
        sats = int(_clamp(round(20 - 6 * hdop + rng.gauss(0.0, 1.0)), 4, 24))
        altitude = 4.0 + 2800.0 * max(0.0, lat - 41.38) + rng.gauss(0.0, 1.5)
        epochs.append(GnssEpoch(t, True, lat, lon, speed, course, round(hdop, 1), sats, altitude))
    return tuple(epochs)


# ---------------------------------------------------------------- vibration


def _riding_vib(street: Street, v: float, vehicle: Vehicle, rng: random.Random) -> float:
    """Vertical RMS (m/s², gravity removed) of one second at speed ``v`` on ``street``."""
    if v < 0.3:
        return _IDLE_VIB_MPS2 * rng.uniform(0.7, 1.4)
    if vehicle is Vehicle.RUN:
        # The stride shakes a runner's Clip far more than any street surface.
        return (4.5 + 0.8 * v) * rng.lognormvariate(0.0, 0.08)
    level = street.vib_rms * math.pow(v / _VIB_REF_SPEED_MS, 0.7) * _VIB_FACTOR[vehicle]
    return level * rng.lognormvariate(0.0, 0.12)


def _shape_peak(ring_s: float, freq_hz: float) -> float:
    """Peak of ``exp(-t/ring) · sin(2πft)``: where ``tan(2πft) = 2πf·ring``."""
    w = 2 * math.pi * freq_hz
    t = math.atan(w * ring_s) / w
    return math.exp(-t / ring_s) * math.sin(w * t)


def _impacts(route: Route, trajectory: Trajectory, world: World, vehicle: Vehicle, rng: random.Random) -> list[Impact]:
    """Shocks before their RMS is known: mapped potholes the rider hits, and unmapped bumps."""
    if vehicle is Vehicle.RUN:
        return []
    factor = _IMPACT_FACTOR[vehicle]
    found: list[Impact] = []

    def hit(s: float, peak_range: tuple[float, float], ring_range: tuple[float, float]) -> None:
        t = trajectory.time_at(s)
        v = trajectory.state_at(t).v
        if v < 1.0:
            return
        peak = rng.uniform(*peak_range) * factor * math.sqrt(v / _VIB_REF_SPEED_MS)
        found.append(Impact(t, peak, rng.uniform(*ring_range), rng.uniform(10.0, 18.0), rms=0.0))

    for pothole in _potholes_on(route, world.potholes):
        s, severity = pothole
        if rng.random() < _POTHOLE_HIT_P[severity]:
            hit(s, _POTHOLE_PEAK_MPS2[severity], (0.06, 0.13))
    for step in route.steps:
        per_m = _BUMPS_PER_KM / 1000 * max(0.0, step.edge.street.vib_rms - _SMOOTH_VIB_MPS2)
        s = step.start_s + (rng.expovariate(per_m) if per_m else math.inf)
        while s < step.start_s + step.edge.length:
            hit(s, (6.0, 14.0), (0.03, 0.06))
            s += rng.expovariate(per_m)
    return sorted(found, key=lambda impact: impact.t)


def _potholes_on(route: Route, potholes: Sequence[Pothole]) -> list[tuple[float, Severity]]:
    return [
        (s, pothole.severity)
        for pothole in potholes
        if (s := route.locate(pothole.position, _POTHOLE_REACH_M)) is not None
    ]


def _with_impacts(base: list[float], impacts: list[Impact], t0: int) -> tuple[tuple[float, ...], tuple[Impact, ...]]:
    """Add each impact's energy (``A²·ring/4``) to the RMS of the second it falls in."""
    energy = [v * v for v in base]
    for impact in impacts:
        energy[min(math.ceil(impact.t) - t0, len(energy) - 1)] += impact.amplitude**2 * impact.ring_s / 4
    rms = tuple(math.sqrt(e) for e in energy)
    placed = tuple(
        Impact(i.t, i.peak, i.ring_s, i.freq_hz, rms[min(math.ceil(i.t) - t0, len(rms) - 1)]) for i in impacts
    )
    return rms, placed


# ---------------------------------------------------------------- sound


def _db_sum(*levels: float) -> float:
    return 10 * math.log10(sum(10 ** (level / 10) for level in levels))


def _noise(
    times: range, streets: Sequence[Street], hour_at: HourAt, rng: random.Random
) -> tuple[tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """LAeq per second, and the ten 100 ms levels inside each second (their energy mean is the LAeq)."""
    decay = math.exp(-1.0 / _NOISE_TAU_S)
    kick = math.sqrt(1.0 - decay * decay) * _NOISE_SIGMA_DB
    drift = 0.0
    event_db, event_left = 0.0, 0
    per_second, per_tenth = [], []
    for t, street in zip(times, streets, strict=True):
        drift = drift * decay + kick * rng.gauss(0.0, 1.0)
        level = street_noise(street, int(hour_at(t))) + drift
        if event_left == 0 and rng.random() < _NOISE_EVENT_P[street.kind]:
            event_db, event_left = level + rng.uniform(4.0, 12.0), rng.randint(1, 3)
        if event_left:
            level = _db_sum(level, event_db)
            event_left -= 1
        tenths = [level + rng.gauss(0.0, 1.2) for _ in range(10)]
        shift = level - _db_sum(*tenths) + 10.0  # energy mean of ten = their sum − 10 dB
        per_second.append(level)
        per_tenth.append(tuple(x + shift for x in tenths))
    return tuple(per_second), tuple(per_tenth)


# ---------------------------------------------------------------- air


def _pm(
    times: range, streets: Sequence[Street], hour_at: HourAt, weather: Weather, rng: random.Random
) -> tuple[PmFrame, ...]:
    """One frame per second: the street's PM2.5, mixed over a few seconds, swollen by humidity."""
    ratio_pm1 = rng.gauss(0.68, 0.03)
    ratio_pm10 = rng.gauss(1.45, 0.06)
    mix = 1.0 - math.exp(-1.0 / _PM_MIX_TAU_S)
    decay = math.exp(-1.0 / _PM_DRIFT_TAU_S)
    kick = math.sqrt(1.0 - decay * decay) * _PM_DRIFT
    spike_decay = math.exp(-1.0 / _PM_SPIKE_TAU_S)
    level = street_pm25(streets[0], int(hour_at(times[0])))
    drift = spike = 0.0
    frames = []
    for t, street in zip(times, streets, strict=True):
        hour = hour_at(t)
        level += (street_pm25(street, int(hour)) - level) * mix
        drift = drift * decay + kick * rng.gauss(0.0, 1.0)
        spike *= spike_decay
        if street.kind in ("arterial", "boulevard") and rng.random() < _PM_SPIKE_P:
            spike += rng.uniform(8.0, 18.0)  # a bus or a delivery van idling next to the rider
        dry = _clamp(level * (1.0 + drift) + spike, *PM25_RANGE)
        swollen = dry * humidity_growth(weather.at(hour)[1])
        frames.append(
            PmFrame(
                _sensor_ugm3(swollen * ratio_pm1, rng),
                _sensor_ugm3(swollen, rng),
                _sensor_ugm3(swollen * ratio_pm10, rng),
            )
        )
    return tuple(frames)


def _sensor_ugm3(value: float, rng: random.Random) -> int:
    """A laser counter's reading: a few percent of noise, whole µg/m³."""
    return max(round(value * rng.gauss(1.0, _PM_SENSOR_NOISE)), 0)


def _battery(t: int, pct: float) -> Battery:
    pct = max(pct, 0.0)
    return Battery(t, pct, battery_mv(pct))


def _jitter_env(reading: tuple[float, float], rng: random.Random) -> tuple[float, float]:
    temp, rh = reading
    return round(temp + rng.gauss(0.0, 0.05), 2), round(_clamp(rh + rng.gauss(0.0, 0.3), 0.0, 100.0), 1)


# ---------------------------------------------------------------- keywords


def _hear(gesture: Gesture, speed_kmh: float, lang: Lang, rng: random.Random) -> KeywordResult | None:
    """The recogniser's answer: wind at speed makes a word harder to catch and less certain."""
    if gesture.said is None:
        return None
    wind = max(0.0, speed_kmh - 8.0)
    if rng.random() > 0.97 - 0.012 * wind:
        return None
    confidence = int(_clamp(round(rng.gauss(93.0 - 1.1 * wind, 7.0)), 1, 100))
    kind = gesture.said
    if rng.random() < 0.03:  # heard as another keyword
        kind = rng.choice([k for k in HazardKind if k not in (HazardKind.NONE, gesture.said)])
    return KeywordResult(kind, confidence, lang)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
