"""Every endpoint the web app calls answers 200 with the shape of src/lib/types.ts."""

import re
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, TypeAdapter
from umi_api.schemas.account import ApiUsage
from umi_api.schemas.activities import ActivityDetail, ActivitySummary
from umi_api.schemas.athletes import Athlete
from umi_api.schemas.city import AirNoiseCell, CityOverview, SafetyData, SurfaceRankRow
from umi_api.schemas.exposure import ExposureSummary
from umi_api.schemas.geojson import FeatureCollection
from umi_api.schemas.health import Health
from umi_api.schemas.profile import ProfileStats
from umi_api.schemas.rider import BestWindow, ClipStatus, WeekStats
from umi_api.schemas.street_map import BrakeHotspot, CityHazard, PlannedRoute, Pothole, StreetSegment

GETS: list[tuple[str, Any]] = [
    ("/healthz", Health),
    ("/readyz", Health),
    ("/v1/me", Athlete),
    ("/v1/athletes/marc", Athlete),
    ("/v1/feed", list[ActivitySummary]),
    ("/v1/activities/laia-20261015-0752", ActivityDetail),
    ("/v1/me/week", WeekStats),
    ("/v1/me/best-window", BestWindow),
    ("/v1/me/clip", ClipStatus),
    ("/v1/streets", list[StreetSegment]),
    ("/v1/potholes", list[Pothole]),
    ("/v1/hotspots/hard-brakes", list[BrakeHotspot]),
    ("/v1/districts", FeatureCollection),
    ("/v1/city-outline", FeatureCollection),
    ("/v1/hazards", list[CityHazard]),
    ("/v1/me/exposure", ExposureSummary),
    ("/v1/me/profile", ProfileStats),
    ("/v1/city/overview", CityOverview),
    ("/v1/city/surface/ranking", list[SurfaceRankRow]),
    ("/v1/city/safety", SafetyData),
    ("/v1/city/hazards", list[CityHazard]),
    ("/v1/city/air-noise", list[list[AirNoiseCell]]),
    ("/v1/account/usage", ApiUsage),
]
# Keys that are not camelCase on purpose: GeoJSON members and district names are data, not fields.
SNAKE_CASE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)+$")


def keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys(v)}
    return set()


@pytest.mark.parametrize(("path", "model"), GETS, ids=[p for p, _ in GETS])
async def test_get_endpoints(client: httpx.AsyncClient, path: str, model: Any) -> None:
    response = await client.get(path)
    assert response.status_code == 200, response.text
    body = response.json()
    TypeAdapter(model).validate_python(body)
    if not path.startswith(("/v1/districts", "/v1/city-outline")):
        assert not {k for k in keys(body) if SNAKE_CASE.match(k)}, "snake_case key in a camelCase API"


async def test_routes(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/routes", json={"from": "Gràcia", "to": "22@", "departAt": "18:30", "via": None})
    assert response.status_code == 200
    routes = TypeAdapter(list[PlannedRoute]).validate_python(response.json())
    assert [r.goal for r in routes] == ["fastest", "calmest", "cleanest"]


@pytest.mark.parametrize("depart_at", ["8:00", "24:00", "noon"])
async def test_routes_reject_a_malformed_departure(client: httpx.AsyncClient, depart_at: str) -> None:
    response = await client.post("/v1/routes", json={"from": "a", "to": "b", "departAt": depart_at})
    assert response.status_code == 422


async def test_optional_fields_are_left_out_rather_than_null(client: httpx.AsyncClient) -> None:
    """TypeScript optional properties (`proof?`, `limit?`, `causes?`...) are absent, never null."""
    overview = (await client.get("/v1/city/overview")).json()
    assert "limit" not in next(k for k in overview["kpis"] if k["id"] == "km")
    assert next(k for k in overview["kpis"] if k["id"] == "pm25")["limit"] == 10
    feed = (await client.get("/v1/feed")).json()
    events = [e for a in feed for e in a["events"]]
    assert all(("cause" in e) == (e["type"] == "hard_brake") for e in events)
    flags = [f for a in feed for f in a["flags"]]
    assert any("proof" in f for f in flags)
    assert all(f.get("proof") is not None for f in flags if "proof" in f)


async def test_streets_bbox(client: httpx.AsyncClient) -> None:
    every = (await client.get("/v1/streets")).json()
    gracia = (await client.get("/v1/streets", params={"bbox": "2.15,41.40,2.17,41.41"})).json()
    assert 0 < len(gracia) < len(every) == 335
    bad = await client.get("/v1/streets", params={"bbox": "2.15,41.40"})
    assert bad.status_code == 422


async def test_exposure_range(client: httpx.AsyncClient) -> None:
    year = (await client.get("/v1/me/exposure")).json()
    month = (await client.get("/v1/me/exposure", params={"range": "30d"})).json()
    assert len(year["days"]) == 365
    assert len(month["days"]) == 30
    assert (await client.get("/v1/me/exposure", params={"range": "1y"})).status_code == 422


@pytest.mark.parametrize("query", [{"period": "1w"}, {"mode": "car"}])
async def test_city_filters_are_validated(client: httpx.AsyncClient, query: dict[str, str]) -> None:
    assert (await client.get("/v1/city/overview", params=query)).status_code == 422


@pytest.mark.parametrize(
    "path", ["/v1/activities/nope", "/v1/athletes/nope", "/v1/nothing-here", "/v1/me/activities/nope/flags/x"]
)
async def test_not_found_is_json(client: httpx.AsyncClient, path: str) -> None:
    response = await (client.post(path, json={"kind": "pothole"}) if "/me/" in path else client.get(path))
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert isinstance(response.json()["detail"], str)


async def test_cors_allows_the_web_app(client: httpx.AsyncClient) -> None:
    preflight = await client.options(
        "/v1/me/activities/x/events/y/cause",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
    other = await client.get("/v1/me", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_response_models_mirror_the_web_types() -> None:
    """Spot-check the field names the web reads, including the ones a generic camelCase would get wrong."""

    def aliases(model: type[BaseModel]) -> set[str]:
        return {field.alias or name for name, field in model.model_fields.items()}

    assert {"hardBrakes30d", "hardBrakesWeek", "answeredBy"} <= aliases(BrakeHotspot)
    assert {"passes30d", "from", "bikeLane", "pm25"} <= aliases(StreetSegment)
    assert {"riders30d", "from", "surfaceIndex"} <= aliases(SurfaceRankRow)
