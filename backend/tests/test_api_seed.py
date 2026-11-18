"""The demo seed and the migrations."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import String, create_engine, func, select
from umi_api.db.base import Base
from umi_api.db.migrate import sync_url
from umi_api.db.models import Activity, HazardConfirmation, HotspotCauseAnswer, RideEvent, StreetSegment
from umi_api.db.session import Database
from umi_api.seed import load_mock_data, seed_demo
from umi_api.seed.shift import MOCK_ANCHOR, parse_instant, week_shift
from umi_api.settings import Settings

MOCK_DATA = Settings().mock_data_dir


def mock_json(name: str) -> Any:
    return json.loads((MOCK_DATA / name).read_text("utf-8"))


@pytest.mark.parametrize(
    ("now", "weeks"),
    [
        (MOCK_ANCHOR - timedelta(days=30), 0),
        (MOCK_ANCHOR, 0),
        (MOCK_ANCHOR + timedelta(days=6, hours=23), 0),
        (MOCK_ANCHOR + timedelta(weeks=1), 1),
        (datetime(2026, 11, 18, 10, tzinfo=UTC), 4),
    ],
)
def test_week_shift(now: datetime, weeks: int) -> None:
    assert week_shift(now) == timedelta(weeks=weeks)


async def test_dates_move_by_whole_weeks(client: httpx.AsyncClient) -> None:
    feed = {a["id"]: a for a in (await client.get("/v1/feed")).json()}
    shift = timedelta(weeks=4)
    for activity in mock_json("activities.json"):
        assert parse_instant(feed[activity["id"]]["startedAt"]) == parse_instant(activity["startedAt"]) + shift
    potholes = {p["id"]: p for p in (await client.get("/v1/potholes")).json()}
    assert potholes["ph-1"]["firstSeen"] == "2026-11-08"  # 2026-10-11 + 28 days
    exposure = (await client.get("/v1/me/exposure")).json()
    assert exposure["days"][-1]["date"] == "2026-11-12"


async def test_seed_is_idempotent(writable_db: str) -> None:
    database = Database(writable_db)

    async def counts() -> tuple[int, ...]:
        async with database.sessions() as session:
            return tuple(
                [
                    await session.scalar(select(func.count()).select_from(model)) or 0
                    for model in (Activity, RideEvent, StreetSegment, HazardConfirmation, HotspotCauseAnswer)
                ]
            )

    before = await counts()
    async with database.sessions() as session:
        report = await seed_demo(session, load_mock_data(MOCK_DATA), datetime(2026, 11, 18, 10, tzinfo=UTC))
    after = await counts()
    await database.dispose()
    assert before == after
    assert report.activities == 31
    assert report.week_shift_days == 28


async def test_seed_matches_the_mock_files(client: httpx.AsyncClient) -> None:
    feed = (await client.get("/v1/feed")).json()
    assert len(feed) == len(mock_json("activities.json")) == 31
    details = mock_json("activity-details.json")
    detail = (await client.get("/v1/activities/marc-20261014-0725")).json()
    assert len(detail["samples"]) == len(details["marc-20261014-0725"]["samples"])
    assert len(detail["route"]) == len(details["marc-20261014-0725"]["route"])
    assert len((await client.get("/v1/streets")).json()) == len(mock_json("streets.json"))
    assert len((await client.get("/v1/hotspots/hard-brakes")).json()) == len(mock_json("hotspots.json"))


def test_migrations_match_the_models(seeded_db: Path) -> None:
    engine = create_engine(sync_url(f"sqlite+aiosqlite:///{seeded_db}"))
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []


def test_seeded_values_fit_their_columns(seeded_db: Path) -> None:
    """SQLite ignores VARCHAR lengths, Postgres enforces them: what loads here must load there."""
    engine = create_engine(sync_url(f"sqlite+aiosqlite:///{seeded_db}"))
    too_long = []
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if isinstance(column.type, String) and column.type.length:
                    longest = connection.scalar(select(func.max(func.length(column))))
                    if longest is not None and longest > column.type.length:
                        too_long.append(f"{table.name}.{column.name}: {longest} > {column.type.length}")
    engine.dispose()
    assert too_long == []
