"""Shared request dependencies: settings, database session, clock, City Insights filters."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.clock import Clock, FixedClock
from umi_api.db.locks import CriticalSection
from umi_api.db.models import Snapshot
from umi_api.db.session import Database
from umi_api.domain.city import CityFilters
from umi_api.domain.enums import Mode, Period
from umi_api.repositories.city import SnapshotRepository
from umi_api.services.street_network import StreetNetwork
from umi_api.settings import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


async def get_session(database: Annotated[Database, Depends(get_database)]) -> AsyncIterator[AsyncSession]:
    async with database.sessions() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_clock(request: Request, settings: SettingsDep, session: SessionDep) -> Clock:
    """The app's clock, or the seeded dataset's moment when the clock is pinned to it."""
    if settings.pin_clock_to_dataset:
        as_of = await SnapshotRepository(session).generated_at(Snapshot.DEMO)
        if as_of is not None:
            return FixedClock(as_of)
    clock: Clock = request.app.state.clock
    return clock


ClockDep = Annotated[Clock, Depends(get_clock)]


def get_wall_clock(request: Request) -> Clock:
    """The app's own clock, never pinned to the demo: an upload or a pairing happens now."""
    clock: Clock = request.app.state.clock
    return clock


WallClockDep = Annotated[Clock, Depends(get_wall_clock)]


def get_street_network(request: Request) -> StreetNetwork:
    network: StreetNetwork = request.app.state.street_network
    return network


StreetNetworkDep = Annotated[StreetNetwork, Depends(get_street_network)]


def get_ingest_section(request: Request) -> CriticalSection:
    """One upload at a time reads and writes hazards, flag counts and activity ids (db.locks)."""
    section: CriticalSection = request.app.state.ingest_section
    return section


IngestSectionDep = Annotated[CriticalSection, Depends(get_ingest_section)]


def city_filters(
    period: Annotated[Period, Query()] = Period.MONTH,
    mode: Annotated[Mode, Query()] = Mode.ALL,
    districts: Annotated[
        str | None, Query(description="Comma-separated district names, as in the City Insights URL")
    ] = None,
) -> CityFilters:
    names = tuple(name.strip() for name in (districts or "").split(",") if name.strip())
    return CityFilters(period=period, mode=mode, districts=names)


CityFiltersDep = Annotated[CityFilters, Depends(city_filters)]
