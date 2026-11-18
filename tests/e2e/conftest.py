"""What the end-to-end tests share: the city, the backend on a seeded database, the firmware SIL program.

The backend runs in-process (ASGI) on a private copy of a database migrated and
seeded once per run, with its wall clock fixed at the seeded demo's "now", so
rides simulated that morning are recent, plausible and inside "this week".
"""

import asyncio
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from umi_api.clock import FixedClock
from umi_api.db import migrate
from umi_api.db.session import Database
from umi_api.main import create_app
from umi_api.seed import load_mock_data, seed_demo
from umi_api.settings import Environment, Settings
from umi_sim.clip import KeyStore
from umi_sim.phone import Phone
from umi_sim.simulation import City

from .demo import API_URL, DEMO_NOW, SEEDED_AT

REPO = Path(__file__).resolve().parents[2]
FIRMWARE = REPO / "firmware"
SIL_PROGRAM = FIRMWARE / ".pio" / "build" / "sil" / "program"


def _settings(database_url: str) -> Settings:
    return Settings(env=Environment.TEST, database_url=database_url)


async def _seed(database_url: str) -> None:
    database = Database(database_url)
    try:
        async with database.sessions() as session:
            await seed_demo(session, load_mock_data(_settings(database_url).mock_data_dir), SEEDED_AT)
    finally:
        await database.dispose()


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("db") / "umi-e2e.db"
    url = f"sqlite+aiosqlite:///{path}"
    migrate.upgrade(url)
    asyncio.run(_seed(url))
    return path


@pytest.fixture
async def api(seeded_db: Path, tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    """The API on a private copy of the seeded database."""
    path = tmp_path / "umi-e2e.db"
    shutil.copyfile(seeded_db, path)
    app = create_app(_settings(f"sqlite+aiosqlite:///{path}"), clock=FixedClock(DEMO_NOW))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=API_URL) as client:
        yield client
    await app.state.database.dispose()


@pytest.fixture
def phone(api: httpx.AsyncClient) -> Phone:
    """The simulator's phone, talking to the in-process API (no retries: there is no network to fail)."""
    return Phone(api, API_URL, attempts=1)


@pytest.fixture(scope="session")
def city() -> City:
    return City.load()


@pytest.fixture
def keys(tmp_path: Path) -> KeyStore:
    """Simulated Clips' keys, private to the test."""
    return KeyStore(tmp_path / "keys")


@pytest.fixture(scope="session")
def sil_program() -> Path:
    """The firmware's SIL program, built (or brought up to date) with PlatformIO; skips without it."""
    pio = shutil.which("pio") or shutil.which("platformio")
    if pio is None:
        pytest.skip("PlatformIO (pio) is not installed: the firmware SIL cannot be built")
    build = subprocess.run(
        [pio, "run", "-e", "sil", "-s"], cwd=FIRMWARE, capture_output=True, text=True, check=False, timeout=900
    )
    assert build.returncode == 0, f"pio run -e sil failed:\n{build.stdout}\n{build.stderr}"
    assert SIL_PROGRAM.is_file(), f"pio run -e sil did not produce {SIL_PROGRAM}"
    return SIL_PROGRAM
