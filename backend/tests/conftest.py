"""One database migrated and seeded per test session; tests that write get a copy of it."""

import asyncio
import json
import shutil
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from umi_api.db import migrate
from umi_api.db.session import Database
from umi_api.main import create_app
from umi_api.seed import load_mock_data, seed_demo
from umi_api.seed.shift import MOCK_ANCHOR, parse_instant, week_shift
from umi_api.settings import Environment, Settings

PARITY_FILE = Path(__file__).parent / "parity" / "mock-responses.json"


def frozen_now() -> datetime:
    """The instant the parity fixture was recorded at: the seed shifts the demo from it, like the mocks did."""
    return parse_instant(json.loads(PARITY_FILE.read_text("utf-8"))["frozenNow"])


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


def make_settings(database_url: str, **overrides: Any) -> Settings:
    return Settings(**{"env": Environment.TEST, "database_url": database_url, **overrides})


@pytest.fixture(scope="session")
def demo_now() -> datetime:
    """The seeded demo's "now", where the API's clock is pinned (UMI_PIN_CLOCK_TO_DATASET)."""
    return MOCK_ANCHOR + week_shift(frozen_now())


async def _seed(database_url: str) -> None:
    database = Database(database_url)
    try:
        async with database.sessions() as session:
            await seed_demo(session, load_mock_data(make_settings(database_url).mock_data_dir), frozen_now())
    finally:
        await database.dispose()


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("db") / "umi-test.db"
    migrate.upgrade(sqlite_url(path))
    asyncio.run(_seed(sqlite_url(path)))
    return path


@pytest.fixture
def writable_db(seeded_db: Path, tmp_path: Path) -> str:
    """A private copy of the seeded database, for tests that change data."""
    path = tmp_path / "umi-test.db"
    shutil.copyfile(seeded_db, path)
    return sqlite_url(path)


async def _client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.database.dispose()


@pytest.fixture
async def client(seeded_db: Path) -> AsyncIterator[httpx.AsyncClient]:
    """Reads the shared seeded database."""
    async for c in _client(make_settings(sqlite_url(seeded_db))):
        yield c


@pytest.fixture
async def writable_client(writable_db: str) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(make_settings(writable_db)):
        yield c


@pytest.fixture
async def writable_database(writable_db: str) -> AsyncIterator[Database]:
    """Direct access to the copy `writable_client` serves, to arrange or inspect rows."""
    database = Database(writable_db)
    yield database
    await database.dispose()


@pytest.fixture
def settings_for() -> Any:
    """Settings for a database URL, with overrides (e.g. `env="production"`)."""
    return make_settings


@pytest.fixture
def seeded_url(seeded_db: Path) -> str:
    return sqlite_url(seeded_db)
