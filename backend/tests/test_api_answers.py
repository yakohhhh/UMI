"""Answers given after a ride: persisted, and only where the app asks."""

import httpx
import pytest
from sqlalchemy import select
from umi_api.db.models import HotspotCauseAnswer, RideEvent
from umi_api.db.session import Database

RIDE = "laia-20261015-0752"
ASKED_BRAKE = f"{RIDE}-e0"
POTHOLE_EVENT = f"{RIDE}-e1"
PRESS_WITHOUT_KEYWORD = f"{RIDE}-f1"
VOICE_FLAG = f"{RIDE}-f0"
MARC_RUN = "marc-20261014-0725"
LAIA = {"Authorization": "Bearer dev:laia"}
MARC = {"Authorization": "Bearer dev:marc"}


def cause_url(activity: str, event: str) -> str:
    return f"/v1/me/activities/{activity}/events/{event}/cause"


def kind_url(activity: str, flag: str) -> str:
    return f"/v1/me/activities/{activity}/flags/{flag}"


async def find(client: httpx.AsyncClient, activity: str, key: str, item_id: str) -> dict[str, object]:
    detail = (await client.get(f"/v1/activities/{activity}")).json()
    return next(item for item in detail[key] if item["id"] == item_id)


async def test_brake_cause_is_persisted(writable_client: httpx.AsyncClient) -> None:
    assert (await find(writable_client, RIDE, "events", ASKED_BRAKE))["cause"] is None
    response = await writable_client.post(cause_url(RIDE, ASKED_BRAKE), json={"cause": "animal"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert (await find(writable_client, RIDE, "events", ASKED_BRAKE))["cause"] == "animal"
    feed = (await writable_client.get("/v1/feed")).json()
    assert next(a for a in feed if a["id"] == RIDE)["events"][0]["cause"] == "animal"
    # Changing one's mind is allowed.
    await writable_client.post(cause_url(RIDE, ASKED_BRAKE), json={"cause": "just_me"})
    assert (await find(writable_client, RIDE, "events", ASKED_BRAKE))["cause"] == "just_me"


async def test_answers_count_in_the_rider_impact(writable_client: httpx.AsyncClient) -> None:
    before = (await writable_client.get("/v1/me/profile")).json()["contributions"]["impact"]["causesGiven"]
    await writable_client.post(cause_url(RIDE, ASKED_BRAKE), json={"cause": "vehicle"})
    after = (await writable_client.get("/v1/me/profile")).json()["contributions"]["impact"]["causesGiven"]
    assert after == before + 1


async def test_flag_kind_is_persisted_and_names_the_hazard(writable_client: httpx.AsyncClient) -> None:
    assert (await find(writable_client, RIDE, "flags", PRESS_WITHOUT_KEYWORD))["kind"] is None
    response = await writable_client.post(kind_url(RIDE, PRESS_WITHOUT_KEYWORD), json={"kind": "pothole"})
    assert response.status_code == 200
    assert (await find(writable_client, RIDE, "flags", PRESS_WITHOUT_KEYWORD))["kind"] == "pothole"
    profile = (await writable_client.get("/v1/me/profile")).json()
    assert next(f for f in profile["contributions"]["flags"] if f["id"] == PRESS_WITHOUT_KEYWORD)["kind"] == "pothole"


@pytest.mark.parametrize(
    ("url", "body", "status"),
    [
        # A pothole is not a brake; only asked brakes take a cause.
        (cause_url(RIDE, POTHOLE_EVENT), {"cause": "surface"}, 409),
        (cause_url("laia-20261012-0754", "laia-20261012-0754-e0"), {"cause": "vehicle"}, 409),
        # The keyword said on the Clip is signed; the rider's answer never overrides it.
        (kind_url(RIDE, VOICE_FLAG), {"kind": "pothole"}, 409),
        # Not the owner: Marc's run is visible to Laia, but only Marc answers for it.
        (kind_url(MARC_RUN, f"{MARC_RUN}-f0"), {"kind": "pothole"}, 403),
        (cause_url(RIDE, "laia-20261014-0754-e0"), {"cause": "animal"}, 404),
        (kind_url(RIDE, "nope"), {"kind": "pothole"}, 404),
        (cause_url("nope", ASKED_BRAKE), {"cause": "animal"}, 404),
        (cause_url(RIDE, ASKED_BRAKE), {"cause": "dog"}, 422),
        (cause_url(RIDE, ASKED_BRAKE), {}, 422),
        (kind_url(RIDE, PRESS_WITHOUT_KEYWORD), {"kind": "graffiti"}, 422),
    ],
)
async def test_answers_are_validated(
    writable_client: httpx.AsyncClient, url: str, body: dict[str, str], status: int
) -> None:
    response = await writable_client.post(url, json=body, headers=LAIA)
    assert response.status_code == status, response.text
    assert "detail" in response.json()


async def test_another_rider_cannot_answer(writable_client: httpx.AsyncClient) -> None:
    response = await writable_client.post(cause_url(RIDE, ASKED_BRAKE), json={"cause": "animal"}, headers=MARC)
    assert response.status_code == 403
    assert (await find(writable_client, RIDE, "events", ASKED_BRAKE))["cause"] is None


async def test_a_cause_at_a_hotspot_joins_its_mix(
    writable_client: httpx.AsyncClient, writable_database: Database
) -> None:
    """Once the pipeline links a brake to a hotspot, the rider's answer counts there (once per brake)."""
    async with writable_database.sessions() as session:
        event = await session.get(RideEvent, ASKED_BRAKE)
        assert event is not None
        event.hotspot_id = "hs-64"
        await session.commit()
    before = next(h for h in (await writable_client.get("/v1/hotspots/hard-brakes")).json() if h["id"] == "hs-64")
    for cause in ("vehicle", "pedestrian"):
        await writable_client.post(cause_url(RIDE, ASKED_BRAKE), json={"cause": cause})
    after = next(h for h in (await writable_client.get("/v1/hotspots/hard-brakes")).json() if h["id"] == "hs-64")
    assert after["answeredBy"] == before["answeredBy"] + 1
    # Her answer is the fifth rider's: the junction's mix can now be published.
    assert before["answeredBy"] == 4
    assert "causes" not in before
    assert "causes" in after
    async with writable_database.sessions() as session:
        answers = (
            await session.scalars(select(HotspotCauseAnswer).where(HotspotCauseAnswer.ride_event_id == ASKED_BRAKE))
        ).all()
    assert [(a.rider_key, a.cause, a.hotspot_id) for a in answers] == [("laia", "pedestrian", "hs-64")]
