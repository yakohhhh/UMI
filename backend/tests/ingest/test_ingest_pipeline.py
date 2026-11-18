"""The pipeline's stages and rules on plain values, without the API or the database."""

import dataclasses
import itertools
import math
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from umi_api.domain.aggregation import HourScores, segment_hour_scores
from umi_api.domain.enums import ActivityType, HazardKind, HazardStatus
from umi_api.domain.hazards import kinds_compatible, status_for
from umi_api.domain.reports import BrakeCandidate, pick_questions
from umi_api.pipeline import (
    SessionRejected,
    StreetIndex,
    StreetRef,
    Track,
    Typical,
    Upload,
    build_track,
    map_match,
    read_upload,
)
from umi_protocol import Activity, DecodedSession, Sample, Session

from .sessions import RideSpec, SoftwareClip, record, streets, trimmed

START = datetime(2026, 11, 12, 7, 30, tzinfo=UTC)
RECEIVED = START + timedelta(hours=2)
# Mallorca south-west to north-east, then right down Passeig de Gràcia: crosses Balmes, Rambla de
# Catalunya and Passeig de Gràcia itself, and turns at a junction where four segments meet.
TURNING = ("seg-047", "seg-048", "seg-049", "seg-156", "seg-157", "seg-158")


def street_index() -> StreetIndex:
    """The seeded network, straight from the web's mock data."""
    typical = Typical(vib_rms=0.8, pm25=12.0, db=65.0, scores=HourScores(60, 60, 60, 60))
    return StreetIndex(
        StreetRef(s["id"], s["name"], s["district"], s["district"], tuple(map(tuple, s["coordinates"])), typical)
        for s in streets().values()
    )


def track_of(spec: RideSpec) -> Track:
    return build_track(read_upload(trimmed(spec, SoftwareClip.numbered(1), 1), accept_simulated=True), RECEIVED)


class TestMapMatching:
    def test_a_noisy_ride_is_matched_to_the_streets_it_took(self) -> None:
        index = street_index()
        noisy = track_of(RideSpec(start=START, segments=TURNING, gnss_noise_m=4.0, seed=7))
        truth = _true_segments(RideSpec(start=START, segments=TURNING), TURNING)
        matched = map_match(noisy, index)

        assert noisy.dropped == 0, "GNSS noise is not a jump"
        assert [run.segment_id for run in matched.runs] == list(TURNING)
        on_the_right_street = sum(
            1 for p, sid in zip(noisy.points, matched.segment_ids, strict=True) if truth.get(p.t_ms) == sid
        )
        # The misses are a fix or two late at junctions, where staying on the current street wins.
        assert on_the_right_street / len(noisy.points) >= 0.95

    def test_heading_keeps_a_ride_on_its_street_across_junctions(self) -> None:
        matched = map_match(track_of(RideSpec(start=START, segments=TURNING[:3], gnss_noise_m=3.0)), street_index())
        names = Counter(streets()[sid]["name"] for sid in matched.segment_ids if sid is not None)
        assert set(names) == {"Carrer de Mallorca"}

    def test_fixes_away_from_any_street_stay_unmatched(self) -> None:
        index = street_index()
        # 45 m into the block north-west of Mallorca (seg-048), 66 m from the nearest other street.
        lon, lat = 2.156412, 41.389745
        assert [c.street.id for c in index.candidates(lon, lat, max_m=50)] == ["seg-048"]
        assert index.nearest(lon, lat) is None


class TestTrack:
    def test_a_gnss_jump_is_dropped_and_the_track_goes_on(self) -> None:
        upload = read_upload(trimmed(RideSpec(start=START), SoftwareClip.numbered(1), 1), accept_simulated=True)
        records = list(upload.session.records)
        i = next(i for i, r in enumerate(records) if isinstance(r, Sample) and r.t_ms == 120_000)
        sample = records[i]
        assert isinstance(sample, Sample)
        # 300 m north in one second: multipath in a street canyon.
        records[i] = dataclasses.replace(sample, lat_e7=sample.lat_e7 + 27_000)
        decoded = upload.session.decoded
        glitched = Upload(Session(DecodedSession(decoded.header, tuple(records), True, None, decoded.end)))

        track = build_track(glitched, RECEIVED)
        assert track.dropped == 1
        assert 120_000 not in {p.t_ms for p in track.points}
        assert track.length_m == pytest.approx(build_track(upload, RECEIVED).length_m, abs=1)

    def test_an_unknown_activity_is_told_by_its_speed(self) -> None:
        def activity(speed_kmh: float) -> ActivityType:
            return track_of(RideSpec(start=START, activity=Activity.UNKNOWN, speed_kmh=speed_kmh)).activity

        assert (activity(18.0), activity(10.0)) == (ActivityType.RIDE, ActivityType.RUN)

    def test_untrimmed_logs_never_reach_the_track(self) -> None:
        with pytest.raises(SessionRejected, match="not trimmed"):
            read_upload(record(RideSpec(start=START), SoftwareClip.numbered(1), 1), accept_simulated=True)


class TestHazardLifecycle:
    @pytest.mark.parametrize(
        ("riders", "status"),
        [
            (1, HazardStatus.PENDING),
            (2, HazardStatus.PENDING),
            (3, HazardStatus.VERIFIED),
            (5, HazardStatus.SENT_TO_CITY),
        ],
    )
    def test_distinct_riders_set_the_status(self, riders: int, status: HazardStatus) -> None:
        assert status_for(HazardStatus.PENDING, riders) is status

    def test_a_hazard_never_moves_back_and_a_closed_one_stays_closed(self) -> None:
        assert status_for(HazardStatus.SENT_TO_CITY, 1) is HazardStatus.SENT_TO_CITY
        assert status_for(HazardStatus.FIXED, 9) is HazardStatus.FIXED

    def test_kinds_join_when_they_agree_or_one_says_nothing(self) -> None:
        assert kinds_compatible(HazardKind.POTHOLE, HazardKind.POTHOLE)
        assert kinds_compatible(None, HazardKind.POTHOLE)
        assert kinds_compatible(HazardKind.POTHOLE, None)
        assert not kinds_compatible(HazardKind.POTHOLE, HazardKind.ROADWORKS)


class TestQuestions:
    def test_unpublished_hotspots_first_then_unexplained_brakes_then_published_hotspots(self) -> None:
        brakes = [
            BrakeCandidate(key=0, decel_mps2=7.0, t_s=10, hotspot_id="hs-1", hotspot_published=True),
            BrakeCandidate(key=1, decel_mps2=4.0, t_s=20),
            BrakeCandidate(key=2, decel_mps2=3.2, t_s=30, hotspot_id="hs-2"),
            BrakeCandidate(key=3, decel_mps2=5.0, t_s=40),
        ]
        assert pick_questions(brakes) == [2, 3]

    def test_one_question_per_hotspot_and_none_for_a_brake_a_flag_explains(self) -> None:
        brakes = [
            BrakeCandidate(key=0, decel_mps2=6.0, t_s=10, explained=True),
            BrakeCandidate(key=1, decel_mps2=4.0, t_s=20, hotspot_id="hs-2"),
            BrakeCandidate(key=2, decel_mps2=5.0, t_s=30, hotspot_id="hs-2"),
            BrakeCandidate(key=3, decel_mps2=3.5, t_s=40),
        ]
        assert pick_questions(brakes) == [2, 3]


@dataclasses.dataclass(frozen=True)
class _Pass:
    athlete_id: str
    activity_type: ActivityType = ActivityType.RIDE
    vib_rms: float | None = 2.4
    pm25: float | None = 30.0
    db: float | None = 75.0
    weighted_brakes: float = 0.0


class TestSegmentHourAnonymity:
    BASELINE = HourScores(comfort=80, safety=70, air=75, noise=65)

    def test_fewer_than_five_distinct_riders_keep_the_baseline(self) -> None:
        one_rider_often = [_Pass("ona")] * 12
        four_riders = [_Pass(f"r{n}") for n in range(4)]
        assert segment_hour_scores(self.BASELINE, one_rider_often) is None
        assert segment_hour_scores(self.BASELINE, four_riders) is None

    def test_five_riders_move_the_scores_towards_what_they_measured(self) -> None:
        scores = segment_hour_scores(self.BASELINE, [_Pass(f"r{n}") for n in range(5)])
        assert scores is not None
        assert scores.comfort < self.BASELINE.comfort
        assert scores.air < self.BASELINE.air
        assert scores.noise < self.BASELINE.noise
        # Nobody braked: safer than the baseline said.
        assert scores.safety > self.BASELINE.safety

    def test_runners_count_as_riders_but_not_for_the_surface(self) -> None:
        runners = [_Pass(f"r{n}", ActivityType.RUN) for n in range(5)]
        scores = segment_hour_scores(self.BASELINE, runners)
        assert scores is not None
        assert (scores.comfort, scores.safety) == (self.BASELINE.comfort, self.BASELINE.safety)
        assert scores.air < self.BASELINE.air


def _true_segments(spec: RideSpec, route: tuple[str, ...]) -> dict[int, str]:
    """The route segment each noise-free fix lies on, by its time."""
    session = Session.from_bytes(record(spec, SoftwareClip.numbered(1), 1))
    truth = {}
    for sample in session.of_type(Sample):
        distances = {sid: _distance_to_line((sample.lon, sample.lat), streets()[sid]["coordinates"]) for sid in route}
        truth[sample.t_ms] = min(distances, key=distances.__getitem__)
    return truth


def _distance_to_line(p: tuple[float, float], line: list[list[float]]) -> float:
    kx, ky = 111_195 * math.cos(math.radians(41.39)), 111_195
    best = math.inf
    for a, b in itertools.pairwise(line):
        ax, ay, bx, by = (a[0] - p[0]) * kx, (a[1] - p[1]) * ky, (b[0] - p[0]) * kx, (b[1] - p[1]) * ky
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best
