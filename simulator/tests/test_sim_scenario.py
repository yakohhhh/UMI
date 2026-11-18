from __future__ import annotations

import dataclasses
import io
import statistics
from itertools import pairwise

import pytest
from umi_protocol.constants import (
    BUTTON_DEBOUNCE_MS,
    BUTTON_DOUBLE_PRESS_GAP_MS,
    BUTTON_HOLD_MS,
    BUTTON_VOICE_WINDOW_MS,
)
from umi_sim.frames import gngga, gnrmc, nmea_checksum, pms_frame
from umi_sim.hazards import Gesture, GestureKind
from umi_sim.scenario import HEADER, write_scenario
from umi_sim.sensors import GnssEpoch, PmFrame
from umi_sim.simulation import SimulatedRide

type Line = tuple[int, str, str]
KINDS = {"imu", "gnss", "pm", "spl", "env", "button", "battery", "keyword"}


@pytest.fixture(scope="module")
def text(commute: SimulatedRide) -> str:
    out = io.StringIO()
    info = write_scenario(commute, out, title="rider=sim-0001 route=Gràcia → 22@ seed=2")
    assert info.lines == out.getvalue().count("\n") - 2
    return out.getvalue()


def _parse(text: str) -> list[Line]:
    parsed = []
    for raw in text.splitlines()[2:]:
        t_ms, kind, fields = raw.split(",", 2)
        parsed.append((int(t_ms), kind, fields))
    return parsed


@pytest.fixture(scope="module")
def lines(text: str) -> list[Line]:
    return _parse(text)


def _of(lines: list[Line], kind: str) -> list[tuple[int, str]]:
    return [(t, fields) for t, k, fields in lines if k == kind]


def _nmea_valid(sentence: str) -> bool:
    body, _, checksum = sentence[1:].partition("*")
    return sentence.startswith("$") and len(checksum) == 2 and nmea_checksum(body) == checksum


def test_header_order_and_kinds(text: str, lines: list[Line]) -> None:
    first, second = text.splitlines()[:2]
    assert first == HEADER
    assert second.startswith("# rider=sim-0001")
    assert all(b[0] >= a[0] for a, b in pairwise(lines))
    assert {kind for _, kind, _ in lines} == KINDS
    assert lines[0][0] == 0


def test_imu_is_100_hz_with_gravity_on_z(lines: list[Line], commute: SimulatedRide) -> None:
    imu = _of(lines, "imu")
    assert [t for t, _ in imu] == list(range(0, imu[-1][0] + 1, 10))
    values = [tuple(map(float, fields.split(","))) for _, fields in imu]
    assert all(len(v) == 6 for v in values)
    at_rest = values[: 3 * 100]  # the Clip wakes before the rider moves off
    assert statistics.mean(v[2] for v in at_rest) == pytest.approx(9.81, abs=0.05)
    assert max(abs(v[0]) for v in at_rest) < 0.5
    # Hard brakes show on x (forward) as a deceleration beyond the threshold.
    t0 = commute.readings.t0
    for brake in commute.readings.brakes:
        start = round((brake.t - t0) * 100)
        window = values[start : start + max(round(brake.duration * 100), 1)]
        assert min(v[0] for v in window) < -3.0


def test_gnss_sentences_are_valid_and_paired(lines: list[Line], commute: SimulatedRide) -> None:
    gnss = _of(lines, "gnss")
    assert len(gnss) == 2 * len(commute.readings.gnss)
    for (t_rmc, rmc), (t_gga, gga) in zip(gnss[::2], gnss[1::2], strict=True):
        assert t_rmc == t_gga
        assert t_rmc % 1000 == 0
        assert rmc.startswith("$GNRMC,")
        assert gga.startswith("$GNGGA,")
        assert _nmea_valid(rmc)
        assert _nmea_valid(gga)
        assert rmc.split(",")[1] == gga.split(",")[1]  # same epoch


def test_nmea_positions_round_trip(commute: SimulatedRide) -> None:
    epoch = next(e for e in commute.readings.gnss if e.fixed)
    fields = gnrmc(epoch, commute.utc(epoch.t)).split(",")
    lat = int(fields[3][:2]) + float(fields[3][2:]) / 60
    lon = int(fields[5][:3]) + float(fields[5][3:]) / 60
    assert (fields[4], fields[6]) == ("N", "E")
    assert lat == pytest.approx(epoch.lat, abs=1e-6)
    assert lon == pytest.approx(epoch.lon, abs=1e-6)
    assert float(fields[7]) * 1852 / 3600 == pytest.approx(epoch.speed, abs=1e-3)


def test_nmea_checksum_matches_published_examples() -> None:
    assert nmea_checksum("GPGLL,5300.97914,N,00259.98174,E,125926,A") == "28"
    assert nmea_checksum("GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,") == "47"


def test_no_fix_sentences_say_so(commute: SimulatedRide) -> None:
    epoch = GnssEpoch(0, False, 0.0, 0.0, 0.0, 0.0, None, 2, 0.0)
    at = commute.depart_utc
    assert gnrmc(epoch, at).split(",")[2] == "V"
    assert gngga(epoch, at).split(",")[6] == "0"


def test_pm_frames_are_valid_plantower_frames(lines: list[Line], commute: SimulatedRide) -> None:
    frames = _of(lines, "pm")
    assert len(frames) == len(commute.readings.pm)
    for (_, hex_frame), reading in zip(frames, commute.readings.pm, strict=True):
        frame = bytes.fromhex(hex_frame)
        assert len(frame) == 32
        assert frame[:4] == b"\x42\x4d\x00\x1c"
        assert sum(frame[:30]) & 0xFFFF == int.from_bytes(frame[30:], "big")
        atmospheric = [int.from_bytes(frame[i : i + 2], "big") for i in (10, 12, 14)]
        assert atmospheric == [reading.pm1, reading.pm25, reading.pm10]


def test_pms_words_saturate() -> None:
    frame = pms_frame(PmFrame(70000, 70000, 70000))
    assert int.from_bytes(frame[4:6], "big") == 0xFFFF


def test_sound_levels_come_ten_per_second(lines: list[Line], commute: SimulatedRide) -> None:
    spl = _of(lines, "spl")
    assert len(spl) == 10 * (len(commute.readings.noise) - 1)
    assert all(b[0] - a[0] == 100 for a, b in pairwise(spl))
    assert all(30.0 < float(level) < 110.0 for _, level in spl)


def test_env_and_battery_every_ten_seconds(lines: list[Line]) -> None:
    for kind, fields_count in (("env", 2), ("battery", 2)):
        entries = _of(lines, kind)
        assert all(b[0] - a[0] == 10_000 for a, b in pairwise(entries))
        assert all(len(fields.split(",")) == fields_count for _, fields in entries)
    assert all(0 <= int(fields.split(",")[1]) <= 100 for _, fields in _of(lines, "battery"))


def _debounced(edges: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Contact states that held for the debounce time, as the firmware's debouncer sees them."""
    stable: list[tuple[int, str]] = []
    for (t, state), following in zip(edges, [*edges[1:], (None, None)], strict=True):
        next_t = following[0]
        if (next_t is None or next_t - t >= BUTTON_DEBOUNCE_MS) and (not stable or stable[-1][1] != state):
            stable.append((t, state))
    return stable


def test_button_gestures_replay_the_rider(lines: list[Line], commute: SimulatedRide) -> None:
    raw = _of(lines, "button")
    stable = _debounced(raw)
    assert [state for _, state in stable] == ["down", "up"] * (len(stable) // 2)
    presses = list(pairwise(stable))[::2]
    expected = [g for g in commute.gestures]
    # A double press is two presses; every other gesture is one.
    assert len(presses) == sum(2 if g.kind is GestureKind.DOUBLE else 1 for g in expected)
    holds = [g for g in expected if g.kind is GestureKind.HOLD]
    long_presses = [(down, up) for (down, _), (up, _) in presses if up - down >= BUTTON_HOLD_MS]
    assert len(long_presses) == len(holds)
    for (first_up, _), (second_down, _) in zip(stable[1::4], stable[2::4], strict=False):
        if second_down - first_up < BUTTON_DOUBLE_PRESS_GAP_MS:
            assert second_down - first_up > 0


def test_keywords_fall_inside_their_voice_window(lines: list[Line]) -> None:
    downs = [t for t, state in _debounced(_of(lines, "button")) if state == "down"]
    keywords = _of(lines, "keyword")
    assert keywords
    for t, fields in keywords:
        kind, confidence, lang = fields.split(",")
        assert kind in {"roadworks", "pothole", "blocked_lane", "obstacle", "danger"}
        assert 0 <= int(confidence) <= 100
        assert lang in {"ca", "es", "en", "fr"}
        down = max(d for d in downs if d < t)
        assert down + BUTTON_HOLD_MS < t < down + BUTTON_HOLD_MS + BUTTON_VOICE_WINDOW_MS


def test_contacts_bounce_now_and_then(commute: SimulatedRide) -> None:
    presses = tuple(Gesture(GestureKind.PRESS, 60.0 + 10 * k) for k in range(20))
    out = io.StringIO()
    write_scenario(dataclasses.replace(commute, gestures=presses), out, title="bounce")
    raw = _of(_parse(out.getvalue()), "button")
    stable = _debounced(raw)
    assert len(raw) > len(stable) == 2 * len(presses)
    assert all(b[0] > a[0] for a, b in pairwise(raw))
