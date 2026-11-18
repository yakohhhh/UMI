"""City Insights. Every figure is aggregated and k-anonymous; filters are period, mode and districts."""

from typing import Annotated

from fastapi import APIRouter, Depends

from umi_api.api.deps import CityFiltersDep, ClockDep, SessionDep
from umi_api.schemas.city import AirNoiseCell, CityOverview, SafetyData, SurfaceRankRow
from umi_api.schemas.street_map import CityHazard
from umi_api.services.city import CityService

router = APIRouter(prefix="/city", tags=["city insights"])


def _city(session: SessionDep, clock: ClockDep) -> CityService:
    return CityService(session, clock)


City = Annotated[CityService, Depends(_city)]


@router.get("/overview", response_model=CityOverview)
async def overview(filters: CityFiltersDep, city: City) -> CityOverview:
    return await city.overview(filters)


@router.get("/surface/ranking", response_model=list[SurfaceRankRow])
async def surface_ranking(filters: CityFiltersDep, city: City) -> list[SurfaceRankRow]:
    """Segments ranked by surface index, roughest first."""
    return await city.surface_ranking(filters)


@router.get("/safety", response_model=SafetyData)
async def safety(filters: CityFiltersDep, city: City) -> SafetyData:
    """Hard-brake hotspots with why riders brake (5+ riders, rounded to 10 %), monthly trend, totals."""
    return await city.safety(filters)


@router.get("/hazards", response_model=list[CityHazard])
async def hazards(filters: CityFiltersDep, city: City) -> list[CityHazard]:
    """Rider flags from 5+ different riders: day-level dates, never who flagged."""
    return await city.hazards(filters)


@router.get("/air-noise", response_model=list[list[AirNoiseCell]])
async def air_noise(filters: CityFiltersDep, city: City) -> list[list[AirNoiseCell]]:
    """Weekday x hour matrix, Monday first."""
    return await city.air_noise(filters)
