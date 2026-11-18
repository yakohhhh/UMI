"""The street map: scored segments, potholes, hotspots, live hazards, boundaries and routes."""

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.clock import Clock
from umi_api.db.models import Hazard
from umi_api.domain.calendar import local_day
from umi_api.domain.enums import CityHazardStatus, Period
from umi_api.domain.geo import BBox, overlaps_bbox
from umi_api.domain.privacy import period_start
from umi_api.domain.reports import MAP_MIN_RIDERS
from umi_api.domain.routes import departure_hour, forecast
from umi_api.repositories.city import CityRepository
from umi_api.repositories.hazards import HazardRepository
from umi_api.repositories.riders import RouteRepository
from umi_api.repositories.streets import HotspotRepository, StreetRepository
from umi_api.schemas import street_map as api
from umi_api.schemas.common import Scores
from umi_api.schemas.geojson import Feature, FeatureCollection
from umi_api.services.errors import NotFoundError
from umi_api.services.hotspots import hotspot_view

UNNAMED_STREET = "Unnamed street"


class MapService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._clock = clock
        self._streets = StreetRepository(session)
        self._hotspots = HotspotRepository(session)
        self._hazards = HazardRepository(session)
        self._city = CityRepository(session)
        self._routes = RouteRepository(session)

    async def streets(self, bbox: BBox | None = None) -> list[api.StreetSegment]:
        potholes = await self._streets.pothole_counts()
        return [
            api.StreetSegment(
                id=s.id,
                name=s.name,
                from_=s.from_name,
                to=s.to_name,
                district=s.district.name,
                kind=s.kind,
                bike_lane=s.bike_lane,
                length_m=s.length_m,
                coordinates=[(p[0], p[1]) for p in s.coordinates],
                scores=Scores(comfort=s.comfort, safety=s.safety, air=s.air, noise=s.noise),
                hourly=api.HourlyScores(
                    comfort=[h.comfort for h in s.hourly],
                    safety=[h.safety for h in s.hourly],
                    air=[h.air for h in s.hourly],
                    noise=[h.noise for h in s.hourly],
                ),
                passes30d=s.passes_30d,
                trend=s.trend,
                surface=api.Surface(vib_rms=s.vib_rms, potholes=potholes.get(s.id, 0)),
                pm25=s.pm25,
                db=s.db,
            )
            for s in await self._streets.segments()
            if bbox is None or overlaps_bbox(s.coordinates, bbox)
        ]

    async def potholes(self) -> list[api.Pothole]:
        return [
            api.Pothole(
                id=p.id,
                segment_id=p.segment_id,
                street=p.segment.name,
                coordinates=(p.lon, p.lat),
                confirmations=p.confirmations,
                first_seen=p.first_seen,
                severity=p.severity,
            )
            for p in await self._streets.potholes()
        ]

    async def hotspots(self) -> list[api.BrakeHotspot]:
        """With why riders brake there over the last 30 days, once enough of them answered."""
        tallies = await self._hotspots.cause_tallies(period_start(self._clock.now(), Period.MONTH))
        return [
            hotspot_view(h, tallies.get(h.id), hard_brakes30d=h.hard_brakes_30d, hard_brakes_week=h.hard_brakes_week)
            for h in await self._hotspots.all()
        ]

    async def live_hazards(self) -> list[api.CityHazard]:
        """Flags on every rider's street map: 3+ different riders, not fixed or gone."""
        return [city_hazard(h, riders) for h, riders in await self._hazards.live(MAP_MIN_RIDERS)]

    async def districts(self) -> FeatureCollection:
        return FeatureCollection(
            features=[
                Feature(properties={"name": d.name, "code": d.code}, geometry=d.geometry)
                for d in await self._city.districts()
            ]
        )

    async def city_outline(self) -> FeatureCollection:
        outlines = await self._city.outlines()
        if not outlines:
            raise NotFoundError("No city outline loaded")
        return FeatureCollection(features=[Feature(properties={"name": o.name}, geometry=o.geometry) for o in outlines])

    async def routes(self, athlete_id: str, request: api.RouteRequest) -> list[api.PlannedRoute]:
        """Fastest / Calmest / Cleanest for the rider's usual trip, forecast for the departure hour.

        The alternatives are precomputed for the rider's commute; routing between
        arbitrary places is a follow-up, so `from`, `to` and `via` don't change them yet.
        """
        hour = departure_hour(request.depart_at)
        routes = []
        for r in await self._routes.planned(athlete_id):
            f = forecast(r, hour)
            routes.append(
                api.PlannedRoute(
                    id=r.id,
                    goal=r.goal,
                    label=r.label,
                    duration_min=f.duration_min,
                    distance_m=r.distance_m,
                    scores=Scores(comfort=f.comfort, safety=f.safety, air=f.air, noise=f.noise),
                    via=r.via,
                    highlight=r.highlight,
                    coordinates=[(p[0], p[1]) for p in r.coordinates],
                )
            )
        return routes


def city_hazard(hazard: Hazard, riders: int) -> api.CityHazard:
    """Day-level dates and never who flagged it."""
    if hazard.kind is None:
        raise ValueError(f"hazard {hazard.id} has no kind and cannot be published")
    return api.CityHazard(
        id=hazard.id,
        kind=hazard.kind,
        street=hazard.street or UNNAMED_STREET,
        district="" if hazard.district is None else hazard.district.name,
        coordinates=(hazard.lon, hazard.lat),
        riders=riders,
        first_seen=local_day(hazard.first_seen_at),
        last_confirmed=local_day(hazard.last_confirmed_at),
        status=hazard.city_status or CityHazardStatus.NEW,
    )
