"""The API answers with the shapes the web app is compiled against.

types.schema.json is generated from src/lib/types.ts (and the few response types
declared in src/lib/api.ts) by `npm run contract:generate`, so this test reads
the TypeScript side itself rather than the backend's own Pydantic mirror of it.
Extra properties are refused: a field the web does not know is a drift too.
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from jsonschema import Draft7Validator

SCHEMA = json.loads((Path(__file__).parent / "types.schema.json").read_text(encoding="utf-8"))


def ref(name: str) -> dict[str, Any]:
    return {"$ref": f"#/definitions/{name}"}


def many(name: str) -> dict[str, Any]:
    return {"type": "array", "items": ref(name)}


GETS: list[tuple[str, dict[str, Any]]] = [
    ("/v1/me", ref("Athlete")),
    ("/v1/athletes/marc", ref("Athlete")),
    ("/v1/feed", many("ActivitySummary")),
    ("/v1/activities/laia-20261015-0752", ref("ActivityDetail")),
    ("/v1/me/week", ref("WeekStats")),
    ("/v1/me/best-window", ref("BestWindow")),
    ("/v1/me/clip", ref("ClipStatus")),
    ("/v1/streets", many("StreetSegment")),
    ("/v1/potholes", many("Pothole")),
    ("/v1/hotspots/hard-brakes", many("BrakeHotspot")),
    ("/v1/hazards", many("CityHazard")),
    ("/v1/me/exposure", ref("ExposureSummary")),
    ("/v1/me/profile", ref("ProfileStats")),
    ("/v1/city/overview?period=30d&mode=all", ref("CityOverview")),
    ("/v1/city/overview?period=7d&mode=bike&districts=Eixample,Gr%C3%A0cia", ref("CityOverview")),
    ("/v1/city/surface/ranking?period=30d&mode=all", many("SurfaceRankRow")),
    ("/v1/city/safety?period=90d&mode=all", ref("SafetyData")),
    ("/v1/city/hazards?period=12m&mode=all", many("CityHazard")),
    ("/v1/city/air-noise?period=30d&mode=all", {"type": "array", "items": many("AirNoiseCell")}),
    ("/v1/account/usage", ref("ApiUsage")),
]


def validate(body: Any, shape: dict[str, Any]) -> list[str]:
    validator = Draft7Validator({**shape, "definitions": SCHEMA["definitions"]})
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in validator.iter_errors(body)][:10]


@pytest.mark.parametrize(("path", "shape"), GETS, ids=[p for p, _ in GETS])
async def test_get_matches_the_web_types(client: httpx.AsyncClient, path: str, shape: dict[str, Any]) -> None:
    response = await client.get(path)
    assert response.status_code == 200, response.text
    assert validate(response.json(), shape) == []


async def test_routes_match_the_web_types(client: httpx.AsyncClient) -> None:
    request = {"from": "Gràcia", "to": "22@", "departAt": "08:30", "via": None}
    assert validate(request, ref("RouteRequest")) == []
    response = await client.post("/v1/routes", json=request)
    assert response.status_code == 200, response.text
    assert validate(response.json(), many("PlannedRoute")) == []
