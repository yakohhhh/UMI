"""Development authentication: `Bearer dev:<athleteId>`, a default rider, nothing in production."""

from pathlib import Path
from typing import Any

import httpx
import pytest
from umi_api.main import create_app


async def me(client: httpx.AsyncClient, headers: dict[str, str] | None = None) -> httpx.Response:
    return await client.get("/v1/me", headers=headers or {})


async def test_default_rider_without_a_header(client: httpx.AsyncClient) -> None:
    assert (await me(client)).json()["id"] == "laia"


async def test_dev_token_selects_the_rider(client: httpx.AsyncClient) -> None:
    response = await me(client, {"Authorization": "Bearer dev:marc"})
    assert response.json()["id"] == "marc"
    feed = (await client.get("/v1/feed", headers={"Authorization": "Bearer dev:marc"})).json()
    assert {a["athleteId"] for a in feed} == {"laia", "marc"}


@pytest.mark.parametrize("token", ["dev:nobody", "secret", "dev:"])
async def test_unknown_or_unsupported_tokens_are_refused(client: httpx.AsyncClient, token: str) -> None:
    response = await me(client, {"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_a_rider_without_a_clip_or_profile_gets_404s(client: httpx.AsyncClient) -> None:
    marc = {"Authorization": "Bearer dev:marc"}
    assert (await client.get("/v1/me/best-window", headers=marc)).status_code == 404
    assert (await client.get("/v1/me/clip", headers=marc)).status_code == 200
    profile = await client.get("/v1/me/profile", headers=marc)
    assert profile.status_code == 200
    assert profile.json()["totals"]["runs"] == 6


@pytest.mark.parametrize("token", [None, "Bearer dev:laia"])
@pytest.mark.parametrize("path", ["/v1/me", "/v1/feed", "/v1/account/usage"])
async def test_production_refuses_dev_auth(seeded_db: Path, settings_for: Any, path: str, token: str | None) -> None:
    app = create_app(settings_for(f"sqlite+aiosqlite:///{seeded_db}", env="production"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path, headers={"Authorization": token} if token else {})
    await app.state.database.dispose()
    assert response.status_code == 401


async def test_public_map_data_needs_no_rider(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/hazards", headers={"Authorization": "Bearer dev:nobody"})
    assert response.status_code == 200
