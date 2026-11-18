"""k-anonymity is counted from distinct riders at query time, never read from a stored status (ADR 0006)."""

from datetime import timedelta

import httpx
from sqlalchemy import delete, select
from umi_api.db.models import Hazard, HazardConfirmation, HotspotCauseAnswer
from umi_api.db.session import Database
from umi_api.domain.enums import (
    ActivityType,
    BrakeCause,
    CityHazardStatus,
    ConfirmationSource,
    HazardKind,
    HazardStatus,
)


async def test_seeded_lists_respect_the_thresholds(client: httpx.AsyncClient) -> None:
    live = (await client.get("/v1/hazards")).json()
    assert live
    assert all(h["riders"] >= 3 for h in live)
    for period in ("7d", "30d", "90d", "12m"):
        for mode in ("all", "bike", "run"):
            city = (await client.get("/v1/city/hazards", params={"period": period, "mode": mode})).json()
            assert all(h["riders"] >= 5 for h in city)
    # Day-level dates only, and never who flagged.
    published = {"id", "kind", "street", "district", "coordinates", "riders", "firstSeen", "lastConfirmed", "status"}
    assert all(set(h) == published for h in live)
    assert all(len(h["firstSeen"]) == 10 for h in live)


async def test_a_stored_status_alone_publishes_nothing(
    writable_client: httpx.AsyncClient, writable_database: Database
) -> None:
    """A hazard marked as sent to the city, with only 4 distinct riders, is on the map but not in City Insights."""
    async with writable_database.sessions() as session:
        source = await session.get(Hazard, "hz-7")
        assert source is not None
        at = source.last_confirmed_at
        session.add(
            Hazard(
                id="hz-test",
                kind=HazardKind.OBSTACLE,
                lon=2.17,
                lat=41.39,
                street="Carrer de Test",
                status=HazardStatus.SENT_TO_CITY,
                city_status=CityHazardStatus.NEW,
                first_seen_at=at,
                last_confirmed_at=at,
            )
        )
        # One rider confirming twice still counts once.
        for rider in ("r1", "r2", "r3", "r4"):
            session.add(
                HazardConfirmation(
                    hazard_id="hz-test",
                    rider_key=rider,
                    activity_type=ActivityType.RIDE,
                    source=ConfirmationSource.SENSOR,
                    confirmed_at=at - timedelta(hours=1),
                )
            )
        await session.commit()
    live = {h["id"]: h for h in (await writable_client.get("/v1/hazards")).json()}
    city = {h["id"] for h in (await writable_client.get("/v1/city/hazards")).json()}
    assert live["hz-test"]["riders"] == 4
    assert "hz-test" not in city

    async with writable_database.sessions() as session:
        session.add(
            HazardConfirmation(
                hazard_id="hz-test",
                rider_key="r5",
                activity_type=ActivityType.RUN,
                source=ConfirmationSource.FLAG,
                confirmed_at=at,
            )
        )
        await session.commit()
    city = {h["id"] for h in (await writable_client.get("/v1/city/hazards")).json()}
    assert "hz-test" in city


async def test_just_me_answers_never_make_a_mix(
    writable_client: httpx.AsyncClient, writable_database: Database
) -> None:
    async with writable_database.sessions() as session:
        await session.execute(delete(HotspotCauseAnswer).where(HotspotCauseAnswer.hotspot_id == "hs-2"))
        recent = (
            await session.scalars(select(HotspotCauseAnswer.answered_at).where(HotspotCauseAnswer.hotspot_id == "hs-1"))
        ).first()
        assert recent is not None
        session.add_all(
            HotspotCauseAnswer(
                hotspot_id="hs-2",
                rider_key=f"r{i}",
                activity_type=ActivityType.RIDE,
                cause=BrakeCause.JUST_ME,
                answered_at=recent,
            )
            for i in range(12)
        )
        await session.commit()
    hotspot = next(h for h in (await writable_client.get("/v1/hotspots/hard-brakes")).json() if h["id"] == "hs-2")
    assert hotspot["answeredBy"] == 0
    assert "causes" not in hotspot
