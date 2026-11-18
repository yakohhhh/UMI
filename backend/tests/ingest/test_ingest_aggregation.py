"""Street scores recomputed from riders' passes, published per segment-hour only from 5 distinct riders."""

from datetime import datetime, timedelta
from typing import Any

import httpx
from umi_api.clock import FixedClock
from umi_api.db.session import Database
from umi_api.domain.aggregation import MIN_RIDERS
from umi_api.domain.numbers import js_round
from umi_api.services.aggregation import AggregationService

from .riders import MakeApi, MakeRider
from .sessions import RideSpec

SEGMENT = "seg-048"
# The corridor is ridden at 08:30-08:37 in Barcelona; seg-048 is passed in the 8 o'clock hour.
HOUR = 8


async def street(api: httpx.AsyncClient, segment_id: str = SEGMENT) -> dict[str, Any]:
    streets: list[dict[str, Any]] = (await api.get("/v1/streets")).json()
    return next(s for s in streets if s["id"] == segment_id)


def bumpy(start: datetime, n: int) -> RideSpec:
    """A ride that felt the street far rougher than its baseline."""
    return RideSpec(start=start + timedelta(minutes=n), vib_mps2=2.5, seed=n)


async def test_a_segment_hour_moves_only_once_five_distinct_riders_passed(
    api: httpx.AsyncClient, make_rider: MakeRider, ride_start: datetime
) -> None:
    before = await street(api)
    regular = await make_rider("ona", 1)
    for n in range(MIN_RIDERS + 2):
        await regular.ride(bumpy(ride_start, n))
    assert (await street(api))["hourly"] == before["hourly"], "one rider, however often, can be told apart"

    for n in range(2, MIN_RIDERS + 1):
        await (await make_rider(f"rider-{n}", n)).ride(bumpy(ride_start, n))
        after = await street(api)
        published = n == MIN_RIDERS
        assert (after["hourly"]["comfort"][HOUR] < before["hourly"]["comfort"][HOUR]) is published, f"{n} riders"

    hourly = after["hourly"]
    assert [h for h in range(24) if hourly["comfort"][h] != before["hourly"]["comfort"][h]] == [HOUR]
    # The all-day scores follow their hours.
    assert after["scores"]["comfort"] == js_round(sum(hourly["comfort"]) / 24)


async def test_without_aggregating_on_ingest_the_scheduled_run_publishes(
    make_api: MakeApi, make_rider: MakeRider, ride_start: datetime, writable_database: Database, demo_now: datetime
) -> None:
    async with await make_api(aggregate_on_ingest=False) as deferred:
        before = await street(deferred)
        for n in range(1, MIN_RIDERS + 1):
            await (await make_rider(f"rider-{n}", n, client=deferred)).ride(bumpy(ride_start, n))
        assert (await street(deferred))["hourly"] == before["hourly"]

        async with writable_database.sessions() as session:
            report = await AggregationService(session, FixedClock(demo_now)).run()
            await session.commit()
        after = await street(deferred)

    assert report.from_riders >= 1
    assert after["hourly"]["comfort"][HOUR] < before["hourly"]["comfort"][HOUR]


async def test_aggregating_the_seeded_demo_changes_nothing(
    api: httpx.AsyncClient, writable_database: Database, demo_now: datetime
) -> None:
    before = (await api.get("/v1/streets")).json()
    async with writable_database.sessions() as session:
        report = await AggregationService(session, FixedClock(demo_now)).run()
        await session.commit()

    assert (report.segments, report.from_riders, report.held_back) == (335, 0, 0)
    assert (await api.get("/v1/streets")).json() == before
