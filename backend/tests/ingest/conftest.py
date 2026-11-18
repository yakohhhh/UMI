"""An API with a fixed wall clock on a private copy of the seeded database, and riders with paired Clips."""

from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

import httpx
import pytest
from umi_api.clock import FixedClock
from umi_api.main import create_app
from umi_api.settings import Settings

from .riders import MakeApi, MakeRider, Rider
from .sessions import SoftwareClip


@pytest.fixture
def ride_start(demo_now: datetime) -> datetime:
    """A morning commute on the demo's day: inside "this week" and the City Insights periods."""
    return demo_now.replace(hour=7, minute=30, second=0, microsecond=0)


@pytest.fixture
async def make_api(
    writable_db: str, settings_for: Callable[..., Settings], demo_now: datetime
) -> AsyncIterator[MakeApi]:
    """API clients on the same database; uploads are received the evening the demo is pinned to."""
    apps = []

    async def make(**overrides: Any) -> httpx.AsyncClient:
        app = create_app(settings_for(writable_db, **overrides), clock=FixedClock(demo_now))
        apps.append(app)
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    yield make
    for app in apps:
        await app.state.database.dispose()


@pytest.fixture
async def api(make_api: MakeApi) -> AsyncIterator[httpx.AsyncClient]:
    async with await make_api() as client:
        yield client


@pytest.fixture
def make_rider(api: httpx.AsyncClient) -> MakeRider:
    """A rider with their own Clip (`n` picks the Clip's key), registered and paired through the dev endpoint."""

    async def make(athlete_id: str, n: int, *, client: httpx.AsyncClient | None = None) -> Rider:
        clip = SoftwareClip.numbered(n)
        response = await api.post("/v1/dev/devices", json=clip.registration(athlete_id))
        assert response.status_code == 201, response.text
        return Rider(athlete_id, clip, client or api)

    return make


@pytest.fixture
async def rider(make_rider: MakeRider) -> Rider:
    return await make_rider("ona", 1)
