"""Flags from uploaded sessions: signatures, undo, the daily cap, and hazards moved by distinct riders."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import httpx
from umi_api.domain.plausibility import MAX_FLAGS_PER_RIDER_DAY
from umi_protocol import HazardKind

from .riders import MakeRider, Rider
from .sessions import Press, RideSpec, Signature

POTHOLE = Press(800, HazardKind.POTHOLE, confidence=90)


async def test_flags_without_a_valid_signature_are_dropped_one_by_one(rider: Rider, ride_start: datetime) -> None:
    presses = (
        Press(500),
        Press(800, signature=Signature.MISSING),
        Press(1100, signature=Signature.FORGED),
    )
    receipt = await rider.ride(RideSpec(start=ride_start, presses=presses))

    assert receipt["flags"] == {"accepted": 1, "rejected": 2}
    ride = await rider.get(f"/v1/activities/{receipt['activityId']}")
    assert [f["id"] for f in ride["flags"]] == [f"{receipt['activityId']}-f0"]


async def test_an_undone_flag_is_neither_kept_nor_rejected(rider: Rider, ride_start: datetime) -> None:
    receipt = await rider.ride(RideSpec(start=ride_start, presses=(Press(600, undone=True), Press(900))))

    assert receipt["flags"] == {"accepted": 1, "rejected": 0}
    ride = await rider.get(f"/v1/activities/{receipt['activityId']}")
    assert [f["id"] for f in ride["flags"]] == [f"{receipt['activityId']}-f1"]


async def test_a_rider_keeps_a_limited_number_of_flags_a_day(rider: Rider, ride_start: datetime) -> None:
    # Far enough apart that each one is its own hazard.
    presses = tuple(Press(300 + 50 * i) for i in range(MAX_FLAGS_PER_RIDER_DAY - 5))
    first = await rider.ride(RideSpec(start=ride_start, presses=presses))
    second = await rider.ride(RideSpec(start=ride_start + timedelta(hours=2), presses=presses[:10]))
    day_before = await rider.ride(RideSpec(start=ride_start - timedelta(days=1), presses=presses[:10]))

    assert first["flags"] == {"accepted": 15, "rejected": 0}
    assert second["flags"] == {"accepted": 5, "rejected": 5}
    assert day_before["flags"] == {"accepted": 10, "rejected": 0}


async def test_distinct_riders_move_a_hazard_to_the_map_then_to_the_city(
    make_rider: MakeRider, api: httpx.AsyncClient, ride_start: datetime
) -> None:
    riders = [await make_rider(f"rider-{n}", n) for n in range(1, 6)]
    first = await riders[0].ride(RideSpec(start=ride_start, presses=(POTHOLE,)))
    hazard_id = f"{first['activityId']}-f0"

    async def first_flag() -> dict[str, Any]:
        flags: list[dict[str, Any]] = (await riders[0].get("/v1/me/profile"))["contributions"]["flags"]
        return next(f for f in flags if f["id"] == hazard_id)

    async def published(path: str) -> list[dict[str, Any]]:
        hazards: list[dict[str, Any]] = (await api.get(path)).json()
        return [h for h in hazards if h["id"] == hazard_id]

    # The same rider flagging the same place again is still one rider.
    again = await riders[0].ride(RideSpec(start=ride_start + timedelta(hours=3), presses=(POTHOLE,)))
    assert again["flags"]["accepted"] == 1
    assert (await first_flag())["status"] == "pending"

    for n, rider in enumerate(riders[1:], start=2):
        # A press without a keyword still confirms a pothole (kinds compatible).
        press = POTHOLE if n % 2 else Press(POTHOLE.at_m)
        await rider.ride(RideSpec(start=ride_start + timedelta(minutes=5 * n), presses=(press,), seed=n))
        flag = await first_flag()
        expected = {2: "pending", 3: "verified", 4: "verified", 5: "sent_to_city"}[n]
        assert (flag["status"], flag["confirmations"]) == (expected, n - 1), f"after {n} riders"
        on_map = await published("/v1/hazards")
        in_city = await published("/v1/city/hazards")
        assert [h["riders"] for h in on_map] == ([n] if n >= 3 else [])
        assert [h["riders"] for h in in_city] == ([n] if n >= 5 else [])

    city = (await published("/v1/city/hazards"))[0]
    assert (city["kind"], city["street"], city["district"], city["status"]) == (
        "pothole",
        "Carrer de Mallorca",
        "Eixample",
        "new",
    )
    assert city["firstSeen"] == city["lastConfirmed"] == ride_start.date().isoformat()


async def test_a_flag_away_from_the_hazard_opens_another(make_rider: MakeRider, ride_start: datetime) -> None:
    ona, pau = await make_rider("ona", 1), await make_rider("pau", 2)
    first = await ona.ride(RideSpec(start=ride_start, presses=(POTHOLE,)))
    second = await pau.ride(RideSpec(start=ride_start, presses=(Press(POTHOLE.at_m + 60, HazardKind.POTHOLE, 90),)))
    third = await pau.ride(RideSpec(start=ride_start, presses=(Press(POTHOLE.at_m, HazardKind.ROADWORKS, 90),)))

    flags = [
        (await r.get(f"/v1/activities/{x['activityId']}"))["flags"][0]
        for r, x in ((ona, first), (pau, second), (pau, third))
    ]
    # 60 m away, and roadworks on a pothole: neither one joins the first hazard.
    assert [f["confirmations"] for f in flags] == [0, 0, 0]


async def test_riders_uploading_at_the_same_moment_join_one_hazard(make_rider: MakeRider, ride_start: datetime) -> None:
    # Each upload reads the open hazards near its ride, then writes; processed side by side,
    # each would miss the hazard the other opened and the corner would end up with three.
    riders = [await make_rider(f"rider-{n}", n) for n in range(1, 4)]
    sessions = [
        r.session(RideSpec(start=ride_start + timedelta(minutes=n), presses=(POTHOLE,), seed=n))
        for n, r in enumerate(riders)
    ]
    responses = await asyncio.gather(*(r.upload(s) for r, s in zip(riders, sessions, strict=True)))
    assert [r.status_code for r in responses] == [201, 201, 201]

    flags = [
        (await r.get(f"/v1/activities/{response.json()['activityId']}"))["flags"][0]
        for r, response in zip(riders, responses, strict=True)
    ]
    assert sorted(f["confirmations"] for f in flags) == [2, 2, 2]
    assert {f["status"] for f in flags} == {"verified"}
