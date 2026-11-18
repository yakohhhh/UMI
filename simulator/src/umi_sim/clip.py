"""A virtual Clip: its identity and keys, and the recorder that writes ``.umis`` sessions.

The recorder follows the firmware's (``firmware/lib/umi_core/src/recorder.c``)
tick by tick on the GNSS epochs: a session starts once the Clip has seen
``motion_start_s`` of movement, writes a SAMPLE every second while recording,
AIR every 10 s and STATUS every 60 s for the whole session, auto-pauses after
``auto_pause_s`` still and ends ``auto_stop_s`` after the rider stopped. EVENTs
follow the ``[detection]`` rules, flags the ``[button]`` rules (as in
``umi_core/src/flags.c``), and every flag is signed with the Clip's P-256 key.
Records come out in time order, as the firmware's reorder buffer writes them.

Simulated Clips set the ``simulated`` header flag and keep their key in a plain
PEM file: they are development devices, which production refuses.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path

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
    KnownRecord,
    Lang,
    RecorderState,
    RecordType,
    Sample,
    SessionWriter,
    State,
    Status,
    StatusFlag,
    TimeSync,
    format_device_id,
    generate_private_key,
    load_private_key_pem,
    parse_device_id,
    private_key_to_pem,
    public_key_to_pem,
    sign_flag,
)
from umi_protocol.constants import (
    BUTTON_KEYWORD_MIN_CONFIDENCE,
    DETECTION_AUTO_PAUSE_S,
    DETECTION_AUTO_STOP_S,
    DETECTION_HARD_BRAKE_MIN_MS,
    DETECTION_HARD_BRAKE_MPS2,
    DETECTION_HARD_BRAKE_REFRACTORY_MS,
    DETECTION_MOTION_START_S,
    DETECTION_MOTION_START_SPEED_KMH,
    DETECTION_POTHOLE_PEAK_MPS2,
    DETECTION_POTHOLE_REFRACTORY_MS,
    DETECTION_POTHOLE_RMS_MPS2,
    FORMAT_HDOP_UNKNOWN,
    FORMAT_NOT_AVAILABLE_U16,
    RATES_AIR_PERIOD_S,
    RATES_STATUS_PERIOD_S,
)

from .hazards import Gesture, GestureKind
from .rider import Vehicle
from .sensors import GnssEpoch, Readings, humidity_growth
from .simulation import SimulatedRide

#: Firmware version simulated Clips report; hardware revision 0 is "devkit / simulator".
FIRMWARE = (0, 1, 0)
HW_REV = 0

# Mirrored from the firmware recorder (recorder.c): without a fix, a Clip this
# calm is lying still; battery and storage thresholds of the STATUS flags.
_STILL_VIB_MPS2 = 0.3
_LOW_BATTERY_PCT = 15
_STORAGE_LOW_KIB = 1024
# brake.c: a deceleration longer than this is reported with this duration.
_MAX_BRAKE_MS = 5000
# Flash left for sessions on an empty Clip, and what a session uses (ADR 0002: ~30 B/s).
_STORAGE_KIB = 12 * 1024
_SESSION_BYTES_PER_S = 30
# The board runs a few degrees above the air and warms up while recording.
_BOARD_HEAT_C = (4.0, 2.0, 600.0)

# Session ids are the session's start minute since this epoch (see VirtualClip.session_id_for).
_SESSION_EPOCH = datetime(2024, 1, 1, tzinfo=UTC)
_RIDER_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_KEYS_DIR_ENV = "UMI_SIM_KEYS_DIR"


@dataclass(frozen=True)
class ClipIdentity:
    """What a Clip gets at provisioning, and the rider it is paired with."""

    rider_id: str
    device_id: int
    serial: str
    private_key: ec.EllipticCurvePrivateKey
    hw_rev: int = HW_REV
    firmware: tuple[int, int, int] = FIRMWARE

    @property
    def device_hex(self) -> str:
        return format_device_id(self.device_id)

    @property
    def firmware_version(self) -> str:
        return ".".join(str(part) for part in self.firmware)

    @property
    def public_key_pem(self) -> str:
        return public_key_to_pem(self.private_key.public_key()).decode("ascii")


def default_keys_dir() -> Path:
    """``$UMI_SIM_KEYS_DIR``, else ``~/.umi-sim/keys``."""
    configured = os.environ.get(_KEYS_DIR_ENV)
    return Path(configured) if configured else Path.home() / ".umi-sim" / "keys"


class UnknownClipError(LookupError):
    """No simulated Clip with that id in the key store, or its files there cannot be read."""


class KeyStore:
    """Simulated Clips on disk: ``<rider>.json`` (identity) and ``<rider>.key.pem`` (private key, mode 0600).

    A rider's Clip is provisioned on first use with a random ``device_id`` and key,
    then reused, so the backend keeps verifying its flags across runs.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def clip_for(self, rider_id: str) -> ClipIdentity:
        if not _RIDER_ID.match(rider_id):
            raise ValueError(f"rider id {rider_id!r}: use lowercase letters, digits and dashes (e.g. sim-0001)")
        meta = self.root / f"{rider_id}.json"
        if meta.exists():
            return self._load(meta)
        identity = ClipIdentity(
            rider_id=rider_id,
            device_id=secrets.randbits(64),
            serial=f"UMI-SIM-{rider_id.removeprefix('sim-').upper()}",
            private_key=generate_private_key(),
        )
        self._save(identity)
        return identity

    def find(self, device_id: int) -> ClipIdentity:
        for meta in sorted(self.root.glob("*.json")):
            # A Clip keeps its key next to its identity; other JSON files here are not Clips.
            if not meta.with_suffix(".key.pem").is_file():
                continue
            identity = self._load(meta)
            if identity.device_id == device_id:
                return identity
        raise UnknownClipError(f"no simulated Clip {format_device_id(device_id)} in {self.root}")

    def _load(self, meta: Path) -> ClipIdentity:
        try:
            raw = json.loads(meta.read_text(encoding="utf-8"))
            key = load_private_key_pem(meta.with_suffix(".key.pem").read_bytes())
            major, minor, patch = (int(part) for part in raw["firmware"].split("."))
            return ClipIdentity(
                rider_id=raw["riderId"],
                device_id=parse_device_id(raw["deviceId"]),
                serial=raw["serial"],
                private_key=key,
                hw_rev=int(raw["hwRev"]),
                firmware=(major, minor, patch),
            )
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise UnknownClipError(f"{meta} is not a readable simulated Clip: {exc!r}") from exc

    def _save(self, identity: ClipIdentity) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        key_path = self.root / f"{identity.rider_id}.key.pem"
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as key_file:
            key_file.write(private_key_to_pem(identity.private_key))
        meta = {
            "riderId": identity.rider_id,
            "deviceId": identity.device_hex,
            "serial": identity.serial,
            "hwRev": identity.hw_rev,
            "firmware": identity.firmware_version,
        }
        (self.root / f"{identity.rider_id}.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True, slots=True)
class Recording:
    """A session as the Clip wrote it."""

    data: bytes
    session_id: int
    started_at: datetime
    duration_ms: int
    events: int
    flags: int
    undos: int


class NoSessionError(RuntimeError):
    """The Clip never saw enough movement with a GNSS fix to start a session."""


class VirtualClip:
    def __init__(self, identity: ClipIdentity) -> None:
        self.identity = identity

    @staticmethod
    def session_id_for(started_at: datetime) -> int:
        """The session's start minute since 2024-01-01 UTC.

        The firmware numbers sessions with a counter; a virtual Clip has no flash to
        keep one in, and numbering by start time keeps ids increasing and never
        reused (a Clip cannot start two sessions in one minute: a session lasts at
        least ``auto_stop_s``) while making re-runs reproducible: uploading the same
        simulated ride twice gives the same ``(device_id, session_id)``, which the
        backend deduplicates.
        """
        if started_at < _SESSION_EPOCH:
            raise ValueError(f"simulated sessions start after {_SESSION_EPOCH:%Y-%m-%d}, not at {started_at}")
        return int((started_at - _SESSION_EPOCH).total_seconds() // 60)

    def record(self, ride: SimulatedRide) -> Recording:
        timeline = _Timeline.of(ride.readings)
        started_at = ride.utc(timeline.start)
        session_id = self.session_id_for(started_at)
        writer = _Writer(self.identity, ride, timeline, session_id)
        records = sorted(writer.records(), key=lambda r: (r.t_ms, _RANK[r.TYPE]))
        header = Header(
            header_flags=HeaderFlag.SIMULATED,
            device_id=self.identity.device_id,
            session_id=session_id,
            activity=ride.spec.vehicle.activity,
            hw_rev=self.identity.hw_rev,
            fw_version=self.identity.firmware,
        )
        sink = io.BytesIO()
        session = SessionWriter(sink, header)
        for record in records:
            session.append(record)
        end = session.finalize(writer.ms(timeline.stop))
        return Recording(
            data=sink.getvalue(),
            session_id=session_id,
            started_at=started_at,
            duration_ms=end.t_ms,
            events=sum(isinstance(r, Event) for r in records),
            flags=sum(isinstance(r, Flag) for r in records),
            undos=sum(isinstance(r, FlagUndo) for r in records),
        )


# Order of records sharing a t_ms. The firmware's reorder queue is stable, so
# ties keep the order of one application step (clip.c): the GNSS fix (time
# sync), the recorder tick (state change, then sample, air, status), the button,
# the detectors.
_RANK = {
    RecordType.TIME_SYNC: 0,
    RecordType.STATE: 1,
    RecordType.SAMPLE: 2,
    RecordType.AIR: 3,
    RecordType.STATUS: 4,
    RecordType.FLAG: 5,
    RecordType.FLAG_UNDO: 6,
    RecordType.EVENT: 7,
}


class _Motion(Enum):
    UNKNOWN = auto()
    MOVING = auto()
    STILL = auto()


def _motion(epoch: GnssEpoch, vib: float) -> _Motion:
    if epoch.fixed:
        return _Motion.MOVING if epoch.speed * 3.6 >= DETECTION_MOTION_START_SPEED_KMH else _Motion.STILL
    return _Motion.STILL if vib < _STILL_VIB_MPS2 else _Motion.UNKNOWN


@dataclass(frozen=True, slots=True)
class _Timeline:
    """When the session starts and stops, its state changes, and the seconds that get a SAMPLE (ride time)."""

    start: int
    stop: int
    states: tuple[tuple[int, RecorderState], ...]
    sample_times: tuple[int, ...]

    @classmethod
    def of(cls, readings: Readings) -> _Timeline:
        moving_since: int | None = None
        still_since: int | None = None
        start: int | None = None
        paused = False
        states: list[tuple[int, RecorderState]] = []
        samples: list[int] = []
        for i, epoch in enumerate(readings.gnss):
            t = readings.t0 + i
            motion = _motion(epoch, readings.vib[i])
            moving_since = (moving_since if moving_since is not None else t) if motion is _Motion.MOVING else None
            still_since = (still_since if still_since is not None else t) if motion is _Motion.STILL else None
            if start is None:
                if moving_since is not None and t - moving_since >= DETECTION_MOTION_START_S:
                    start = t
                    states.append((t, RecorderState.RECORDING))
                continue
            if not paused:
                if still_since is not None and t - still_since >= DETECTION_AUTO_PAUSE_S:
                    paused = True
                    states.append((t, RecorderState.AUTO_PAUSE))
                else:
                    samples.append(t)
            elif moving_since is not None:
                # The schedule restarts on the next whole second after the resume.
                paused = False
                states.append((t, RecorderState.RESUME))
            elif still_since is not None and t - still_since >= DETECTION_AUTO_STOP_S:
                return cls(start, t, tuple(states), tuple(samples))
        if start is None:
            raise NoSessionError("the rider never moved long enough with a GNSS fix")
        return cls(start, readings.end, tuple(states), tuple(samples))


class _Writer:
    """Builds every record of one session from the readings (not yet in time order)."""

    def __init__(self, identity: ClipIdentity, ride: SimulatedRide, timeline: _Timeline, session_id: int) -> None:
        self.identity = identity
        self.ride = ride
        self.readings = ride.readings
        self.timeline = timeline
        self.session_id = session_id

    def ms(self, t: float) -> int:
        return round((t - self.timeline.start) * 1000)

    def in_session(self, t: float) -> bool:
        return self.timeline.start <= t <= self.timeline.stop

    def records(self) -> Iterator[KnownRecord]:
        yield from (State(self.ms(t), state) for t, state in self.timeline.states)
        yield from self._time_sync()
        yield from (self._sample(t) for t in self.timeline.sample_times)
        yield from self._periodic()
        yield from self._events()
        yield from self._flags()

    def _time_sync(self) -> Iterator[TimeSync]:
        # The fix that completes the motion window is read before the tick that
        # starts the session, so the first fix the session sees is a later one.
        r = self.readings
        for epoch in r.gnss[r.index(self.timeline.start) + 1 :]:
            if epoch.fixed:
                unix_ms = (int(self.ride.depart_utc.timestamp()) + epoch.t) * 1000
                yield TimeSync(self.ms(epoch.t), unix_ms)
                return

    def _sample(self, t: int) -> Sample:
        i = self.readings.index(t)
        epoch = self.readings.gnss[i]
        common = {
            "t_ms": self.ms(t),
            "vib_mms2": _u16(self.readings.vib[i] * 1000),
            "noise_cdba": _u16(self.readings.noise[i] * 100),
            "sats": epoch.sats,
        }
        if not epoch.fixed:
            return Sample(
                lat_e7=0, lon_e7=0, speed_cms=0, heading_cdeg=0, hdop_d=FORMAT_HDOP_UNKNOWN, fix=Fix.NONE, **common
            )
        return Sample(
            lat_e7=round(epoch.lat * 1e7),
            lon_e7=round(epoch.lon * 1e7),
            speed_cms=_u16(epoch.speed * 100),
            heading_cdeg=round(epoch.course * 100) % 36000,
            hdop_d=_hdop_d(epoch.hdop),
            fix=Fix.THREE_D if epoch.sats >= 4 else Fix.TWO_D,
            **common,
        )

    def _periodic(self) -> Iterator[Air | Status]:
        start, stop = self.timeline.start, self.timeline.stop
        # The stop tick closes the session before the schedule runs (recorder.c).
        for t in range(start, stop):
            elapsed = t - start
            if elapsed and elapsed % RATES_AIR_PERIOD_S == 0:
                yield self._air(t)
            if elapsed % RATES_STATUS_PERIOD_S == 0:
                yield self._status(t)

    def _air(self, t: int) -> Air:
        """The PM frames since the previous AIR, averaged; PM2.5 corrected for humidity like air.c."""
        r = self.readings
        frames = r.pm[r.index(max(t - RATES_AIR_PERIOD_S, self.timeline.start)) + 1 : r.index(t) + 1]
        env = r.env_at(t)
        if not frames:
            pm1 = pm25 = pm10 = FORMAT_NOT_AVAILABLE_U16
        else:
            n = len(frames)
            pm1 = _u16(sum(f.pm1 for f in frames) / n * 10)
            pm25 = _u16(sum(f.pm25 for f in frames) / n / humidity_growth(env.rh_pct) * 10)
            pm10 = _u16(sum(f.pm10 for f in frames) / n * 10)
        return Air(self.ms(t), pm1, pm25, pm10, round(env.temp_c * 100), _u16(env.rh_pct * 10))

    def _status(self, t: int) -> Status:
        battery = self.readings.battery_at(t)
        elapsed = t - self.timeline.start
        free_kib = _STORAGE_KIB - elapsed * _SESSION_BYTES_PER_S // 1024
        flags = StatusFlag(0)
        if battery.pct < _LOW_BATTERY_PCT:
            flags |= StatusFlag.LOW_BATTERY
        if free_kib < _STORAGE_LOW_KIB:
            flags |= StatusFlag.STORAGE_LOW
        offset, warm_up, tau = _BOARD_HEAT_C
        board_c = self.readings.env_at(t).temp_c + offset + warm_up * (1 - math.exp(-elapsed / tau))
        return Status(self.ms(t), round(battery.pct), flags, battery.mv, round(board_c * 100), free_kib)

    def _last_fix(self, t: float) -> GnssEpoch | None:
        r = self.readings
        for epoch in reversed(r.gnss[: r.index(math.floor(t)) + 1]):
            if epoch.fixed:
                return epoch
        return None

    def _position_e7(self, t: float) -> tuple[int, int]:
        fix = self._last_fix(t)
        return (0, 0) if fix is None else (round(fix.lat * 1e7), round(fix.lon * 1e7))

    def _events(self) -> Iterator[Event]:
        quiet_until = -math.inf
        for brake in self.readings.brakes:
            if not self.in_session(brake.t) or brake.t < quiet_until:
                continue
            if brake.mean <= DETECTION_HARD_BRAKE_MPS2 or brake.duration * 1000 < DETECTION_HARD_BRAKE_MIN_MS:
                continue
            quiet_until = brake.t + brake.duration + DETECTION_HARD_BRAKE_REFRACTORY_MS / 1000
            duration_ms = min(round(brake.duration * 1000), _MAX_BRAKE_MS)
            mean, peak = _u16(brake.mean * 1000), _u16(brake.peak * 1000)
            yield Event(self.ms(brake.t), EventKind.HARD_BRAKE, mean, peak, duration_ms, *self._position_e7(brake.t))
        if self.ride.spec.vehicle is Vehicle.RUN:
            # A runner's stride passes the pothole test at every step: the detector is for rides.
            return
        quiet_until = -math.inf
        for impact in self.readings.impacts:
            if not self.in_session(impact.t) or impact.t < quiet_until:
                continue
            if impact.rms < DETECTION_POTHOLE_RMS_MPS2 or impact.peak < DETECTION_POTHOLE_PEAK_MPS2:
                continue
            quiet_until = impact.t + DETECTION_POTHOLE_REFRACTORY_MS / 1000
            rms, peak = _u16(impact.rms * 1000), _u16(impact.peak * 1000)
            duration_ms = round(impact.duration_s * 1000)
            yield Event(self.ms(impact.t), EventKind.POTHOLE, rms, peak, duration_ms, *self._position_e7(impact.t))

    def _flags(self) -> Iterator[Flag | FlagUndo]:
        seq = 0
        last_seq: int | None = None
        for gesture in self.ride.gestures:
            if not self.in_session(gesture.t):
                continue
            if gesture.kind is GestureKind.DOUBLE:
                if last_seq is not None:
                    yield FlagUndo(self.ms(gesture.t), last_seq)
                    last_seq = None  # an undo cancels the last flag, once
                continue
            yield sign_flag(
                self.identity.private_key, self.identity.device_id, self.session_id, self._flag(gesture, seq)
            )
            last_seq = seq
            seq += 1

    def _flag(self, gesture: Gesture, seq: int) -> Flag:
        r = self.readings
        fix = self._last_fix(gesture.t)
        i = r.index(math.floor(gesture.t))
        source, kind, confidence, lang = FlagSource.PRESS, HazardKind.NONE, 0, Lang.NONE
        if gesture.kind is GestureKind.HOLD:
            source = FlagSource.VOICE
            if (heard := r.keywords.get(gesture)) is not None:
                # Kept below the threshold too: it shows how the recogniser does in the field.
                confidence, lang = heard.confidence, heard.lang
                if heard.kind != HazardKind.NONE and heard.confidence >= BUTTON_KEYWORD_MIN_CONFIDENCE:
                    kind = heard.kind
        lat_e7, lon_e7 = self._position_e7(gesture.t)
        return Flag(
            t_ms=self.ms(gesture.t),
            seq=seq,
            source=source,
            kind=kind,
            confidence=confidence,
            lang=lang,
            lat_e7=lat_e7,
            lon_e7=lon_e7,
            speed_cms=0 if fix is None else _u16(fix.speed * 100),
            vib_mms2=_u16(r.vib[i] * 1000),
            noise_cdba=_u16(r.noise[i] * 100),
        )


def _u16(value: float) -> int:
    """A measurement in its wire unit; 0xFFFF means "not available", so readings saturate below it."""
    return min(max(round(value), 0), FORMAT_NOT_AVAILABLE_U16 - 1)


def _hdop_d(hdop: float | None) -> int:
    return FORMAT_HDOP_UNKNOWN if hdop is None else min(round(hdop * 10), FORMAT_HDOP_UNKNOWN - 1)
