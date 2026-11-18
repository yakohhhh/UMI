"""The backend answers what the web app's mocks answered (tests/parity/mock-responses.json).

The fixture is recorded from src/lib/api.ts at a frozen instant; the test
database is seeded from the same JSON at that instant. Known, deliberate
differences are spelled out where they are compared.
"""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from umi_api.domain.calendar import local_clock_time
from umi_api.seed.shift import parse_instant

PARITY: dict[str, Any] = json.loads((Path(__file__).parent / "parity" / "mock-responses.json").read_text("utf-8"))
CITY_CASES = PARITY["city"]


def city_query(filters: dict[str, Any]) -> dict[str, str]:
    """How the web app serialises CityFilters (src/lib/api.ts)."""
    query = {"period": filters["period"], "mode": filters["mode"]}
    if filters["districts"]:
        query["districts"] = ",".join(filters["districts"])
    return query


def without(value: Any, *keys: str) -> Any:
    """`value` with `keys` dropped at every depth."""
    if isinstance(value, dict):
        return {k: without(v, *keys) for k, v in value.items() if k not in keys}
    if isinstance(value, list):
        return [without(v, *keys) for v in value]
    return value


async def get(client: httpx.AsyncClient, path: str, **params: str) -> Any:
    response = await client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ("key", "path"),
    [
        ("me", "/v1/me"),
        ("marc", "/v1/athletes/marc"),
        ("week", "/v1/me/week"),
        ("bestWindow", "/v1/me/best-window"),
        ("clip", "/v1/me/clip"),
        ("potholes", "/v1/potholes"),
        ("exposure", "/v1/me/exposure"),
        ("usage", "/v1/account/usage"),
    ],
)
async def test_identical_to_the_mock(client: httpx.AsyncClient, key: str, path: str) -> None:
    assert await get(client, path) == PARITY[key]


async def test_feed(client: httpx.AsyncClient) -> None:
    feed = await get(client, "/v1/feed")
    assert [a["id"] for a in feed] == [a["id"] for a in PARITY["feed"]]
    # Event and flag times follow the shifted start (see test_times_follow_the_shifted_start).
    assert without(feed, "time") == without(PARITY["feed"], "time")


@pytest.mark.parametrize("activity_id", sorted(PARITY["activities"]))
async def test_activity_detail(client: httpx.AsyncClient, activity_id: str) -> None:
    detail = await get(client, f"/v1/activities/{activity_id}")
    expected = PARITY["activities"][activity_id]
    assert len(detail["samples"]) == len(expected["samples"])
    assert without(detail, "time") == without(expected, "time")


async def test_times_follow_the_shifted_start(client: httpx.AsyncClient) -> None:
    """The mocks keep the original HH:mm strings, which drift by an hour once the shift crosses a DST change.

    The backend stores instants (start + the sample's clock) and formats them in Barcelona time.
    """
    for activity in await get(client, "/v1/feed"):
        detail = await get(client, f"/v1/activities/{activity['id']}")
        started = parse_instant(detail["startedAt"])
        for item in detail["events"] + detail["flags"]:
            seconds = detail["samples"][item["sampleIndex"]][0]
            assert item["time"] == local_clock_time(started + timedelta(seconds=seconds))


async def test_profile(client: httpx.AsyncClient) -> None:
    assert without(await get(client, "/v1/me/profile"), "time") == without(PARITY["profile"], "time")


@pytest.mark.parametrize("case", PARITY["routes"], ids=lambda c: c["departAt"] or "default")
async def test_routes(client: httpx.AsyncClient, case: dict[str, Any]) -> None:
    body = {"from": "Gràcia", "to": "22@"} | ({"departAt": case["departAt"]} if case["departAt"] else {})
    response = await client.post("/v1/routes", json=body)
    assert response.status_code == 200
    assert response.json() == case["routes"]


async def test_live_hazards(client: httpx.AsyncClient) -> None:
    """Same hazards; the backend lists the most confirmed first instead of the mocks' file order."""
    hazards = await get(client, "/v1/hazards")
    assert sorted(hazards, key=lambda h: h["id"]) == sorted(PARITY["liveHazards"], key=lambda h: h["id"])


async def test_hotspots(client: httpx.AsyncClient) -> None:
    assert_hotspots(await get(client, "/v1/hotspots/hard-brakes"), PARITY["hotspots"], same_riders=True)


@pytest.mark.parametrize("case", CITY_CASES, ids=lambda c: "-".join(city_query(c["filters"]).values()))
async def test_city_overview_surface_and_air(client: httpx.AsyncClient, case: dict[str, Any]) -> None:
    query = city_query(case["filters"])
    assert await get(client, "/v1/city/overview", **query) == case["overview"]
    assert await get(client, "/v1/city/surface/ranking", **query) == case["surfaceRanking"]
    assert await get(client, "/v1/city/air-noise", **query) == case["airNoise"]


@pytest.mark.parametrize("case", CITY_CASES, ids=lambda c: "-".join(city_query(c["filters"]).values()))
async def test_city_safety(client: httpx.AsyncClient, case: dict[str, Any]) -> None:
    safety = await get(client, "/v1/city/safety", **city_query(case["filters"]))
    expected = case["safety"]
    assert safety["monthly"] == expected["monthly"]
    assert safety["totals"] == expected["totals"]
    # The mocks rescaled answer counts by mode; the backend counts the riders on each kind of activity.
    assert_hotspots(safety["hotspots"], expected["hotspots"], same_riders=case["filters"]["mode"] == "all")


@pytest.mark.parametrize("case", CITY_CASES, ids=lambda c: "-".join(city_query(c["filters"]).values()))
async def test_city_hazards(client: httpx.AsyncClient, case: dict[str, Any]) -> None:
    hazards = await get(client, "/v1/city/hazards", **city_query(case["filters"]))
    if case["filters"]["mode"] == "bike":
        # The mocks counted every rider for "Bike"; the backend counts riders on a bike only.
        assert [h["id"] for h in hazards] == [h["id"] for h in case["hazards"]]
        assert all(h["riders"] <= m["riders"] for h, m in zip(hazards, case["hazards"], strict=True))
        assert without(hazards, "riders") == without(case["hazards"], "riders")
    else:
        assert hazards == case["hazards"]


def assert_hotspots(hotspots: list[dict[str, Any]], expected: list[dict[str, Any]], *, same_riders: bool) -> None:
    """Counts match; cause mixes follow the privacy rule.

    The mocks published idealised mixes; the backend rounds real per-rider answer
    counts, so a share can differ by 10 % (hs-1, whose mix the mocks fixed, matches).
    """
    assert without(hotspots, "causes", "answeredBy") == without(expected, "causes", "answeredBy")
    for got, want in zip(hotspots, expected, strict=True):
        if same_riders:
            assert got["answeredBy"] == want["answeredBy"]
            assert ("causes" in got) == ("causes" in want)
        if "causes" in got:
            assert got["answeredBy"] >= 5
            assert_publishable_mix(got["causes"])
        if same_riders and got["id"] == "hs-1":
            assert got["causes"] == want["causes"]


def assert_publishable_mix(causes: list[dict[str, Any]]) -> None:
    names = [c["cause"] for c in causes]
    assert len(set(names)) == len(names)
    assert "just_me" not in names
    assert len([n for n in names if n != "other"]) <= 4
    assert all(round(c["share"] * 10) == pytest.approx(c["share"] * 10) and c["share"] >= 0.1 for c in causes)
    assert sum(c["share"] for c in causes) == pytest.approx(1)
