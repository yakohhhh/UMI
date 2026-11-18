from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from datetime import date

import pytest
from umi_protocol import Air, Event, EventKind, Sample, Session
from umi_sim.clip import ClipIdentity, Recording, VirtualClip
from umi_sim.geo import to_xy
from umi_sim.scores import Scores, brakes_from_safety_score, db_from_noise_score, pm_from_air_score
from umi_sim.sensors import (
    NOISE_RANGE,
    PM25_RANGE,
    Weather,
    battery_mv,
    humidity_growth,
    street_noise,
    street_pm25,
)
from umi_sim.simulation import City, RideSpec, SimulatedRide, simulate


def test_conversions_match_score_ts() -> None:
    # Values computed with src/lib/score.ts.
    assert pm_from_air_score(100) == 5.0
    assert pm_from_air_score(0) == 36.3
    assert pm_from_air_score(64) == 16.3
    assert db_from_noise_score(100) == 50.0
    assert db_from_noise_score(67) == 60.0
    assert brakes_from_safety_score(55) == 10.0
    assert brakes_from_safety_score(100) == 0.0
    assert Scores(comfort=84, safety=55, air=64, noise=67).overall == 65


def test_street_levels_stay_in_the_product_ranges(city: City) -> None:
    for street in city.world.streets:
        for hour in range(24):
            assert PM25_RANGE[0] <= street_pm25(street, hour) <= PM25_RANGE[1]
            assert NOISE_RANGE[0] <= street_noise(street, hour) <= NOISE_RANGE[1]


def test_recorded_air_and_noise_are_in_range(recording: Recording) -> None:
    session = Session.from_bytes(recording.data)
    pm25 = [a.pm25_ugm3 for a in session.of_type(Air) if a.pm25_ugm3 is not None]
    # The laser counter reports whole µg/m³ before the humidity correction: allow that rounding.
    assert pm25
    assert all(PM25_RANGE[0] - 1 <= v <= PM25_RANGE[1] + 1 for v in pm25)
    noise = [s.noise_dba for s in session.of_type(Sample) if s.noise_dba is not None]
    inside = [v for v in noise if NOISE_RANGE[0] <= v <= NOISE_RANGE[1]]
    # Street levels stay in range; a horn or a motorbike now and then goes above.
    assert len(inside) / len(noise) > 0.95
    assert max(noise) < 95


def test_pm_follows_the_street_through_the_humidity_correction(commute: SimulatedRide, recording: Recording) -> None:
    session = Session.from_bytes(recording.data)
    recorded = statistics.median(a.pm25_ugm3 for a in session.of_type(Air) if a.pm25_ugm3 is not None)
    route = commute.route
    expected = statistics.median(street_pm25(step.edge.street, 7) for step in route.steps)
    assert recorded == pytest.approx(expected, rel=0.25)


@pytest.fixture(scope="module")
def events(city: City, make_spec: Callable[..., RideSpec], identity: ClipIdentity) -> list[Event]:
    clip = VirtualClip(identity)
    return [
        event
        for seed in range(8)
        for event in Session.from_bytes(clip.record(simulate(city, make_spec(seed=seed))).data).of_type(Event)
    ]


def test_events_follow_the_detection_rules(events: list[Event]) -> None:
    assert {e.kind for e in events} == {EventKind.HARD_BRAKE, EventKind.POTHOLE}
    for event in events:
        if event.kind is EventKind.HARD_BRAKE:
            assert event.value_mms2 > 3000
            assert event.duration_ms >= 300
        else:
            assert event.value_mms2 >= 4000
            assert event.peak_mms2 >= 12000
        assert event.peak_mms2 >= event.value_mms2


def test_gnss_fixes_follow_the_route(commute: SimulatedRide) -> None:
    fixed = [e for e in commute.readings.gnss if e.fixed]
    assert len(fixed) > 0.9 * len(commute.readings.gnss)
    for epoch in fixed:
        _, off = commute.route.line.project(to_xy(epoch.lon, epoch.lat))
        assert off < 30.0
        assert epoch.hdop is not None
        assert 0.5 <= epoch.hdop <= 5.0
        assert epoch.sats >= 4


def test_vibration_rises_with_impacts(commute: SimulatedRide) -> None:
    r = commute.readings
    for impact in r.impacts:
        assert r.vib[r.index(impact.t)] == pytest.approx(impact.rms)
        assert impact.rms**2 >= impact.amplitude**2 * impact.ring_s / 4


def test_humidity_growth_is_what_the_clip_divides_by() -> None:
    assert humidity_growth(0.0) == 1.0
    assert humidity_growth(70.0) == pytest.approx(1 + 0.38 * 0.7 / 0.3)
    assert humidity_growth(100.0) == humidity_growth(95.0)


def test_weather_is_the_same_for_everyone_on_a_day() -> None:
    day = date(2026, 11, 18)
    assert Weather.on(day) == Weather.on(day)
    temp, rh = Weather.on(day).at(15.0)
    assert 5.0 < temp < 25.0
    assert 25.0 <= rh <= 95.0
    assert Weather.on(date(2026, 7, 18)).temp_c > Weather.on(date(2026, 1, 18)).temp_c


def test_battery_voltage_follows_charge() -> None:
    assert battery_mv(100) > battery_mv(50) > battery_mv(5) > battery_mv(0)
    assert battery_mv(0) > 3200
    assert battery_mv(100) < 4200
    assert math.isclose(battery_mv(150), battery_mv(100))
