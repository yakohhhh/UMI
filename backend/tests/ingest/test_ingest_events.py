"""Ride events from uploaded sessions: the Clip's, the derived ones, and the brakes the app asks about."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from umi_api.db.models import RideEvent, SegmentPass
from umi_api.db.session import Database
from umi_api.domain.reports import MAX_QUESTIONS_PER_RIDE

from .riders import Rider
from .sessions import Brake, Press, RideSpec, Stretch

# Comte d'Urgell × Mallorca (hs-16, its cause mix already published) is 270 m along the corridor.
AT_PUBLISHED_HOTSPOT = Brake(270, 7.0)
AWAY = (Brake(600, 4.0), Brake(900, 5.5), Brake(1200, 4.5), Brake(1500, 3.5))


def asked_at(ride: dict[str, Any], spec: RideSpec) -> list[float]:
    """Where along the route the brakes the app asks about happened."""
    brakes = [e for e in ride["events"] if e["type"] == "hard_brake"]
    assert len(brakes) == len(spec.brakes)
    by_time = sorted(spec.brakes, key=lambda b: b.at_m)
    return sorted(b.at_m for b, e in zip(by_time, brakes, strict=True) if e["ask"])


async def test_at_most_two_brakes_are_asked_about_the_most_informative_first(
    rider: Rider, ride_start: datetime
) -> None:
    spec = RideSpec(start=ride_start, brakes=(AT_PUBLISHED_HOTSPOT, *AWAY))
    receipt = await rider.ride(spec)
    ride = await rider.get(f"/v1/activities/{receipt['activityId']}")

    # Away from any hotspot, the hardest ones; the harder brake at a published junction tells little new.
    assert asked_at(ride, spec) == [900, 1200]
    assert MAX_QUESTIONS_PER_RIDE == 2


async def test_a_brake_a_flag_explains_is_not_asked_about(rider: Rider, ride_start: datetime) -> None:
    # Pressed 10 s after the 900 m brake.
    spec = RideSpec(start=ride_start, brakes=AWAY, presses=(Press(950),))
    receipt = await rider.ride(spec)
    ride = await rider.get(f"/v1/activities/{receipt['activityId']}")

    assert asked_at(ride, spec) == [600, 1200]


async def test_spikes_and_peaks_are_derived_once_per_episode(rider: Rider, ride_start: datetime) -> None:
    spec = RideSpec(
        start=ride_start,
        # Recorded twice by the Clip: one brake.
        brakes=(Brake(700), Brake(700)),
        smoky=(Stretch(400, 500),),
        # At 18 km/h: 12 s of quiet joins the first two, over two minutes splits off the third.
        loud=(Stretch(600, 640), Stretch(700, 740), Stretch(1400, 1440)),
    )
    receipt = await rider.ride(spec)
    ride = await rider.get(f"/v1/activities/{receipt['activityId']}")

    assert [(e["type"], e["value"]) for e in ride["events"]] == [
        ("pm_spike", 40.0),
        ("noise_peak", 84.0),
        ("hard_brake", 4.0),
        ("noise_peak", 84.0),
    ]
    assert receipt["events"] == 4


async def test_a_cause_reweighs_the_brake_in_its_street_pass(
    rider: Rider, ride_start: datetime, writable_database: Database
) -> None:
    receipt = await rider.ride(RideSpec(start=ride_start, brakes=(Brake(900, 5.5),)))
    ride = await rider.get(f"/v1/activities/{receipt['activityId']}")
    brake = ride["events"][0]

    async def weighted() -> float:
        async with writable_database.sessions() as session:
            query = select(SegmentPass.weighted_brakes).join(RideEvent).where(RideEvent.id == brake["id"])
            weight: float = (await session.execute(query)).scalar_one()
            return weight

    assert await weighted() == 0.5, "unanswered brakes count half"
    for cause, weight in (("just_me", 0.0), ("vehicle", 1.0)):
        answer = await rider.client.post(
            f"/v1/me/activities/{ride['id']}/events/{brake['id']}/cause", json={"cause": cause}, headers=rider.auth
        )
        assert answer.status_code == 200, answer.text
        assert await weighted() == weight
