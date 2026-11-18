"""Pure rules, ported from the web app (reference values computed with src/lib/*.ts)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest
from umi_api.domain import enums
from umi_api.domain.calendar import day_month, iso_utc, local_clock_time, local_day
from umi_api.domain.enums import ActivityType, BrakeCause, HazardKind, HazardStatus, RideEventType
from umi_api.domain.exposure import exposure_report
from umi_api.domain.impact import Impact, impact
from umi_api.domain.numbers import js_number, js_round, round_to
from umi_api.domain.privacy import OTHER, cause_mix
from umi_api.domain.reports import brake_weight, can_answer_cause, can_answer_kind, moments_to_check
from umi_api.domain.routes import departure_hour, forecast
from umi_api.domain.scoring import (
    air_score_from_pm,
    brakes_from_safety_score,
    comfort_score_from_vib,
    noise_score_from_db,
    overall_score,
)
from umi_api.domain.week import week_summary
from umi_protocol import constants


@dataclass(frozen=True)
class S:
    comfort: int
    safety: int
    air: int
    noise: int


def test_js_rounding() -> None:
    assert [js_round(v) for v in (2.5, -2.5, 0.5, 1.4999, -0.5)] == [3, -2, 1, 1, 0]
    assert round_to(23.45, 1) == 23.5
    assert [js_number(v) for v in (7, 7.0, 7.5, -3.0)] == ["7", "7", "7.5", "-3"]


def test_scores_match_score_ts() -> None:
    cases = [(72, 64, 58, 61), (90, 95, 92, 88), (20, 15, 30, 10), (50, 50, 50, 50), (84, 55, 64, 67)]
    assert [overall_score(S(*c)) for c in cases] == [64, 93, 7, 47, 65]
    assert [overall_score(S(100, 100, 100, 100)), overall_score(S(0, 0, 0, 0))] == [100, 0]
    assert [air_score_from_pm(v) for v in (5, 12.3, 35, 40)] == [100, 77, 4, 0]
    assert [noise_score_from_db(v) for v in (50, 63.9, 80, 85)] == [100, 54, 1, 0]
    assert [comfort_score_from_vib(v) for v in (0.4, 0.81, 1.5, 3.5)] == [100, 84, 58, 0]
    assert [brakes_from_safety_score(v) for v in (100, 55, 0, 77.5)] == [0, 10, 22, 5]


def test_enums_follow_the_wire_codes() -> None:
    """Names shared with the Clip must match protocol/constants.toml."""
    assert {k.value for k in HazardKind} == {m.name.lower() for m in constants.HazardKind if m.value}
    assert {s.value for s in enums.FlagSource} == {m.name.lower() for m in constants.FlagSource}
    assert {a.value for a in ActivityType} == {m.name.lower() for m in constants.Activity if m.value}
    assert {m.name.lower() for m in constants.EventKind} <= {e.value for e in RideEventType}


class TestCauseMix:
    def test_below_the_city_threshold_nothing_is_published(self) -> None:
        assert cause_mix({BrakeCause.VEHICLE: 4}, riders=4) is None
        assert cause_mix({BrakeCause.JUST_ME: 9}, riders=9) is None

    def test_shares_are_rounded_to_ten_percent_and_small_causes_merged(self) -> None:
        mix = cause_mix(
            {
                BrakeCause.VEHICLE: 11,
                BrakeCause.PEDESTRIAN: 6,
                BrakeCause.JUNCTION: 6,
                BrakeCause.ANIMAL: 3,
                BrakeCause.CAR_DOOR: 1,
                BrakeCause.ROADWORKS: 1,
            },
            riders=28,
        )
        assert mix is not None
        assert [(c.cause, c.share) for c in mix] == [
            (BrakeCause.VEHICLE, 0.4),
            (BrakeCause.PEDESTRIAN, 0.2),
            (BrakeCause.JUNCTION, 0.2),
            (BrakeCause.ANIMAL, 0.1),
            (OTHER, 0.1),
        ]

    def test_just_me_is_left_out(self) -> None:
        mix = cause_mix({BrakeCause.VEHICLE: 5, BrakeCause.JUST_ME: 50}, riders=5)
        assert mix is not None
        assert [(c.cause, c.share) for c in mix] == [(BrakeCause.VEHICLE, 1.0)]

    def test_at_most_four_named_causes(self) -> None:
        mix = cause_mix({cause: 1 for cause in BrakeCause if cause is not BrakeCause.JUST_ME}, riders=8)
        assert mix is not None
        assert len(mix) == 5
        assert mix[-1].cause == OTHER
        assert sum(c.share for c in mix) == pytest.approx(1)

    def test_rounding_overshoot_comes_off_the_largest(self) -> None:
        # 3 x 1/3 rounds to 3 x 0.3 + 0.1 other; 2 x 0.45 + 0.1 rounds to 0.5 + 0.5 + 0.1.
        mix = cause_mix({BrakeCause.VEHICLE: 9, BrakeCause.PEDESTRIAN: 9, BrakeCause.ANIMAL: 2}, riders=20)
        assert mix is not None
        assert [(c.cause, c.share) for c in mix] == [
            (BrakeCause.VEHICLE, 0.4),
            (BrakeCause.PEDESTRIAN, 0.5),
            (BrakeCause.ANIMAL, 0.1),
        ]


@dataclass(frozen=True)
class Event:
    type: RideEventType
    ask: bool
    cause: BrakeCause | None


@dataclass(frozen=True)
class FlagState:
    keyword_kind: HazardKind | None
    kind: HazardKind | None


def test_report_rules() -> None:
    assert brake_weight(None) == constants.REPORTS_UNANSWERED_BRAKE_WEIGHT
    assert brake_weight(BrakeCause.JUST_ME) == 0
    assert brake_weight(BrakeCause.ANIMAL) == brake_weight(BrakeCause.SURFACE) == 1
    asked = Event(RideEventType.HARD_BRAKE, ask=True, cause=None)
    assert can_answer_cause(asked)
    assert not can_answer_cause(Event(RideEventType.HARD_BRAKE, ask=False, cause=None))
    assert not can_answer_cause(Event(RideEventType.POTHOLE, ask=True, cause=None))
    pressed = FlagState(keyword_kind=None, kind=None)
    assert can_answer_kind(pressed)
    assert not can_answer_kind(FlagState(keyword_kind=HazardKind.ROADWORKS, kind=HazardKind.ROADWORKS))
    assert (
        moments_to_check([asked, Event(RideEventType.HARD_BRAKE, ask=True, cause=BrakeCause.VEHICLE)], [pressed]) == 2
    )


@dataclass(frozen=True)
class Outcome:
    status: HazardStatus
    riders_warned: int


def test_impact_counts_outcomes_not_presses() -> None:
    flags = [Outcome(HazardStatus.PENDING, 0), Outcome(HazardStatus.VERIFIED, 57), Outcome(HazardStatus.FIXED, 640)]
    assert impact(Impact(10, 1, 1, 1), flags, causes_given=2) == Impact(707, 3, 2, 3)


def test_barcelona_calendar() -> None:
    summer = datetime(2026, 10, 15, 5, 52, 40, tzinfo=UTC)
    winter = datetime(2026, 11, 12, 5, 52, 40, tzinfo=UTC)
    assert (local_clock_time(summer), local_clock_time(winter)) == ("07:52", "06:52")
    assert local_day(datetime(2026, 11, 12, 23, 30, tzinfo=UTC)) == date(2026, 11, 13)
    assert day_month(date(2026, 9, 14)) == "14 Sept"
    assert iso_utc(datetime(2026, 11, 12, 5, 52, 40, 123456, tzinfo=UTC)) == "2026-11-12T05:52:40.123Z"


@dataclass(frozen=True)
class Ride:
    type: ActivityType
    started_at: datetime
    distance_m: int
    moving_time_s: int


def test_week_starts_on_monday_in_barcelona() -> None:
    now = datetime(2026, 11, 12, 17, tzinfo=UTC)  # Thursday
    rides = [
        Ride(ActivityType.RIDE, datetime(2026, 11, 8, 23, 30, tzinfo=UTC), 1000, 60),  # Monday 00:30 local
        Ride(ActivityType.RIDE, datetime(2026, 11, 8, 22, 30, tzinfo=UTC), 5000, 60),  # Sunday, last week
        Ride(ActivityType.RUN, datetime(2026, 11, 12, 7, tzinfo=UTC), 3650, 600),
    ]
    week = week_summary(rides, now)
    assert (week.distance_km, week.rides, week.runs, week.moving_time_s) == (4.7, 1, 1, 660)
    assert [d.km for d in week.days] == [1.0, 0, 0, 3.7, 0, 0, 0]
    assert [d.is_today for d in week.days].index(True) == 3


@dataclass(frozen=True)
class Day:
    day: date
    ride_min: int
    pm25: float | None
    db: float | None


def test_exposure_is_weighted_by_riding_time() -> None:
    days = [
        Day(date(2026, 11, 9), 30, 10.0, 60.0),
        Day(date(2026, 11, 10), 10, 20.0, 70.0),
        Day(date(2026, 11, 11), 0, None, None),
    ]
    report = exposure_report(days)
    assert [(w.start, w.label, w.pm25, w.db, w.ride_min) for w in report.weekly] == [
        ("2026-11-09", "9 Nov", 12.5, 62.5, 40)
    ]
    assert report.totals.riding_days == 2
    assert report.totals.avg_pm25 == 12.5


@dataclass(frozen=True)
class Route:
    duration_min: int
    comfort: int
    safety: int
    air: int
    noise: int


def test_route_forecast() -> None:
    peak = Route(18, 66, 61, 54, 43)
    assert forecast(peak, departure_hour(None)) == forecast(peak, 8)
    night = forecast(peak, 2)
    assert night.duration_min < 18
    assert (night.comfort, night.safety, night.air, night.noise) == (69, 74, 69, 63)
