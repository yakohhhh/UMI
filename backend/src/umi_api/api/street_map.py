from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from umi_api.api.auth import CurrentAthlete
from umi_api.api.deps import ClockDep, SessionDep
from umi_api.domain.geo import BBox
from umi_api.schemas.geojson import FeatureCollection
from umi_api.schemas.street_map import BrakeHotspot, CityHazard, PlannedRoute, Pothole, RouteRequest, StreetSegment
from umi_api.services.street_map import MapService

router = APIRouter(tags=["street map"])


def _map(session: SessionDep, clock: ClockDep) -> MapService:
    return MapService(session, clock)


Map = Annotated[MapService, Depends(_map)]


def _bbox(
    bbox: Annotated[str | None, Query(description="minLon,minLat,maxLon,maxLat")] = None,
) -> BBox | None:
    if bbox is None:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = (float(part) for part in bbox.split(","))
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="bbox must be minLon,minLat,maxLon,maxLat"
        ) from exc
    return min_lon, min_lat, max_lon, max_lat


@router.get("/streets", response_model=list[StreetSegment])
async def streets(map_: Map, bbox: Annotated[BBox | None, Depends(_bbox)]) -> list[StreetSegment]:
    """Scored street segments with their 24-hour profiles."""
    return await map_.streets(bbox)


@router.get("/potholes", response_model=list[Pothole])
async def potholes(map_: Map) -> list[Pothole]:
    return await map_.potholes()


@router.get("/hotspots/hard-brakes", response_model=list[BrakeHotspot])
async def hard_brake_hotspots(map_: Map) -> list[BrakeHotspot]:
    """With why riders brake there (last 30 days), once 5+ different riders answered."""
    return await map_.hotspots()


@router.get("/hazards", response_model=list[CityHazard])
async def live_hazards(map_: Map) -> list[CityHazard]:
    """Live flags on every rider's street map: 3+ different riders, not fixed or gone."""
    return await map_.live_hazards()


@router.get("/districts", response_model=FeatureCollection)
async def districts(map_: Map) -> FeatureCollection:
    """District boundaries (GeoJSON)."""
    return await map_.districts()


@router.get("/city-outline", response_model=FeatureCollection)
async def city_outline(map_: Map) -> FeatureCollection:
    return await map_.city_outline()


@router.post("/routes", response_model=list[PlannedRoute])
async def routes(request: RouteRequest, athlete_id: CurrentAthlete, map_: Map) -> list[PlannedRoute]:
    """Fastest / Calmest / Cleanest alternatives, forecast for the departure time."""
    return await map_.routes(athlete_id, request)
