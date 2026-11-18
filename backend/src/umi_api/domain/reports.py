"""Rider flags and "why did you brake?" answers (port of src/lib/reports.ts).

A hard brake is a measured fact; its cause is context. A dog crossing is not a
false positive: it still counts for the junction, it just gets a reason. Only
"just me" leaves street data, and it stays in the rider's own report.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from umi_protocol import constants

from umi_api.domain.enums import BrakeCause, CauseBucket, HazardKind, RideEventType

# Different riders before a flag shows on everyone's street map (same rule as potholes).
MAP_MIN_RIDERS = constants.PRIVACY_MAP_MIN_RIDERS
# Different riders before a flag or a cause mix reaches City Insights.
CITY_MIN_RIDERS = constants.PRIVACY_CITY_MIN_RIDERS
MAX_QUESTIONS_PER_RIDE = constants.REPORTS_MAX_QUESTIONS_PER_RIDE
# A hard brake this close to a hotspot is one of that junction's brakes. Hotspots are
# junctions at least ~50 m apart; 40 m covers a chamfered Cerdà crossing and its approach.
HOTSPOT_RADIUS_M = 40.0
# A flag pressed this soon after a hard brake already says what it was about.
FLAG_EXPLAINS_BRAKE_S = 30

CAUSE_BUCKET: dict[BrakeCause, CauseBucket] = {
    BrakeCause.PEDESTRIAN: CauseBucket.BEHAVIOUR,
    BrakeCause.ANIMAL: CauseBucket.BEHAVIOUR,
    BrakeCause.VEHICLE: CauseBucket.BEHAVIOUR,
    BrakeCause.CAR_DOOR: CauseBucket.BEHAVIOUR,
    BrakeCause.LANE_BLOCKED: CauseBucket.INFRASTRUCTURE,
    BrakeCause.SURFACE: CauseBucket.INFRASTRUCTURE,
    BrakeCause.ROADWORKS: CauseBucket.INFRASTRUCTURE,
    BrakeCause.JUNCTION: CauseBucket.INFRASTRUCTURE,
    BrakeCause.JUST_ME: CauseBucket.PERSONAL,
}


class BrakeQuestion(Protocol):
    @property
    def type(self) -> RideEventType: ...
    @property
    def ask(self) -> bool: ...
    @property
    def cause(self) -> BrakeCause | None: ...


class FlagQuestion(Protocol):
    @property
    def keyword_kind(self) -> HazardKind | None: ...
    @property
    def kind(self) -> HazardKind | None: ...


def brake_weight(cause: BrakeCause | None) -> float:
    """Weight of a hard brake in a junction's safety score, by what we know about its cause."""
    if cause is None:
        return constants.REPORTS_UNANSWERED_BRAKE_WEIGHT
    return 0.0 if CAUSE_BUCKET[cause] is CauseBucket.PERSONAL else 1.0


def can_answer_cause(event: BrakeQuestion) -> bool:
    """Only the hard brakes the app asked about can be given a cause (answers may be changed)."""
    return event.type is RideEventType.HARD_BRAKE and event.ask


def can_answer_kind(flag: FlagQuestion) -> bool:
    """Only flags pressed without a recognised keyword are answered after the ride.

    The keyword is part of the Clip's signed record; the rider's answer never overrides it.
    """
    return flag.keyword_kind is None


def moments_to_check(events: Iterable[BrakeQuestion], flags: Iterable[FlagQuestion]) -> int:
    """Moments left to answer on a ride: unanswered asked brakes, then flags pressed without a keyword."""
    brakes = sum(1 for e in events if e.ask and e.cause is None)
    return brakes + sum(1 for f in flags if f.kind is None)


@dataclass(frozen=True)
class BrakeCandidate:
    """A hard brake of the ride being processed, with what is known about where it happened."""

    key: int
    decel_mps2: float
    t_s: float
    hotspot_id: str | None = None
    # The hotspot's cause mix is already published (enough different riders answered there).
    hotspot_published: bool = False
    # A flag pressed right after it says what it was about.
    explained: bool = False


def pick_questions(brakes: Iterable[BrakeCandidate], limit: int = MAX_QUESTIONS_PER_RIDE) -> list[int]:
    """The hard brakes the app asks "why did you brake?" about after the ride, at most `limit` (their keys).

    The answers worth most come first:
    1. a brake at a hotspot whose cause mix is not published yet: it brings the junction
       closer to the riders it needs;
    2. a brake away from any hotspot: nothing explains it, so the answer is new information;
    3. a brake at a hotspot whose mix is already published.
    Within a rank, the harder brake, then the earlier one. A brake a flag already explains
    is not asked about (the flag is), and a ride is asked about one brake per hotspot at most.
    """

    def rank(brake: BrakeCandidate) -> tuple[int, float, float]:
        place = 1 if brake.hotspot_id is None else (2 if brake.hotspot_published else 0)
        return place, -brake.decel_mps2, brake.t_s

    picked: list[int] = []
    hotspots: set[str] = set()
    for brake in sorted((b for b in brakes if not b.explained), key=rank):
        if len(picked) == limit:
            break
        if brake.hotspot_id is not None:
            if brake.hotspot_id in hotspots:
                continue
            hotspots.add(brake.hotspot_id)
        picked.append(brake.key)
    return picked
