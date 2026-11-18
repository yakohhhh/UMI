"""City Insights: overview, surface ranking, safety, rider-flagged hazards, air and noise."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.clock import Clock
from umi_api.db.models import BrakeHotspot, CityKpi, District, DistrictStats, Snapshot
from umi_api.domain import city as rules
from umi_api.domain.calendar import local_day, local_midnight
from umi_api.domain.city_alerts import city_alerts
from umi_api.domain.enums import ActivityType, Mode
from umi_api.domain.privacy import PERIOD_DAYS, period_start
from umi_api.domain.reports import CITY_MIN_RIDERS
from umi_api.repositories.city import CityRepository, SnapshotRepository
from umi_api.repositories.hazards import HazardRepository
from umi_api.repositories.streets import HotspotRepository, StreetRepository
from umi_api.schemas import city as api
from umi_api.schemas.common import Scores
from umi_api.schemas.street_map import CityHazard
from umi_api.services.hotspots import hotspot_view
from umi_api.services.street_map import city_hazard

_ACTIVITY_OF_MODE = {Mode.ALL: None, Mode.BIKE: ActivityType.RIDE, Mode.RUN: ActivityType.RUN}


class CityService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._clock = clock
        self._city = CityRepository(session)
        self._snapshots = SnapshotRepository(session)
        self._streets = StreetRepository(session)
        self._hotspots = HotspotRepository(session)
        self._hazards = HazardRepository(session)

    async def overview(self, f: rules.CityFilters) -> api.CityOverview:
        """KPIs over the selected districts; every district is returned (maps need the whole city)."""
        hotspots = await self._hotspots.all()
        active = [h for h in hotspots if h.hard_brakes_week >= rules.ACTIVE_HOTSPOT_PER_WEEK]
        districts = [
            _district_figures(d, d.stats, f, sum(1 for h in active if h.district_code == d.code))
            for d in await self._city.districts()
            if d.stats is not None
        ]
        kpis = rules.district_kpis([rules.scale_kpi(_kpi(k), f) for k in await self._city.kpis()], districts, f)
        published = [h for h in await self._published_hazards() if f.includes(h.district)]
        alerts = city_alerts(
            [[cell.pm25 for cell in row] for row in await self._city.air_noise()],
            hotspots,
            await self._ranking(),
            published,
        )
        generated_at = await self._snapshots.generated_at(Snapshot.CITY) or self._clock.now()
        return api.CityOverview(
            kpis=[api.Kpi.model_validate(k) for k in kpis],
            districts=[_district_stat(d) for d in districts],
            alerts=[api.CityAlert.model_validate(a) for a in alerts],
            generated_at=generated_at,
        )

    async def surface_ranking(self, f: rules.CityFilters) -> list[api.SurfaceRankRow]:
        if f.mode is Mode.RUN:
            # Runners don't measure surface vibration.
            return []
        rows = []
        for row in await self._ranking():
            if not f.includes(row.district):
                continue
            impacts, riders = rules.scale_surface(row.confirmed_impacts, row.riders30d, f)
            rows.append(row.model_copy(update={"confirmed_impacts": impacts, "riders30d": riders}))
        return rows

    async def safety(self, f: rules.CityFilters) -> api.SafetyData:
        hotspots = await self._hotspots.all()
        selected = [h for h in hotspots if f.includes(_district_name(h))]
        share = len(selected) / len(hotspots) if f.districts and hotspots else 1
        monthly = rules.monthly_brakes(await self._city.monthly_brakes(), f, share)
        tallies = await self._hotspots.cause_tallies(
            period_start(self._clock.now(), f.period), _ACTIVITY_OF_MODE[f.mode]
        )
        views = []
        for h in selected:
            brakes, week = rules.scale_hotspot(h.hard_brakes_30d, h.hard_brakes_week, f)
            views.append(hotspot_view(h, tallies.get(h.id), hard_brakes30d=brakes, hard_brakes_week=week))
        totals = rules.safety_totals(monthly, views, f)
        return api.SafetyData(
            hotspots=views,
            monthly=[api.MonthlyBrakes.model_validate(m) for m in monthly],
            totals=api.SafetyTotals.model_validate(totals),
        )

    async def hazards(self, f: rules.CityFilters) -> list[CityHazard]:
        """Flags from 5+ different riders confirmed during the period: day-level dates, no reporters."""
        since = local_midnight(local_day(self._clock.now() - timedelta(days=PERIOD_DAYS[f.period])))
        rows = await self._hazards.sent_to_city(
            CITY_MIN_RIDERS, confirmed_since=since, activity_type=_ACTIVITY_OF_MODE[f.mode]
        )
        return [h for h in (city_hazard(hazard, riders) for hazard, riders in rows) if f.includes(h.district)]

    async def air_noise(self, f: rules.CityFilters) -> list[list[api.AirNoiseCell]]:
        """Hour x weekday, Monday first."""
        matrix = rules.scale_air_noise(await self._city.air_noise(), f)
        return [[api.AirNoiseCell.model_validate(cell) for cell in row] for row in matrix]

    async def _ranking(self) -> list[api.SurfaceRankRow]:
        return [
            api.SurfaceRankRow(
                segment_id=s.segment_id,
                street=s.segment.name,
                from_=s.segment.from_name,
                to=s.segment.to_name,
                district=s.segment.district.name,
                surface_index=s.surface_index,
                confirmed_impacts=s.confirmed_impacts,
                riders30d=s.riders_30d,
                trend=s.trend,
                length_m=s.segment.length_m,
            )
            for s in await self._streets.surface_ranking()
        ]

    async def _published_hazards(self) -> list[CityHazard]:
        return [city_hazard(h, riders) for h, riders in await self._hazards.sent_to_city(CITY_MIN_RIDERS)]


def _district_name(hotspot: BrakeHotspot) -> str | None:
    return None if hotspot.district is None else hotspot.district.name


def _kpi(row: CityKpi) -> rules.Kpi:
    return rules.Kpi(
        id=row.id,
        label=row.label,
        value=row.value,
        unit=row.unit,
        delta=row.delta,
        delta_unit=row.delta_unit,
        better=row.better,
        spark=list(row.spark),
        delta_label=row.delta_label,
        limit=row.limit_value,
        limit_label=row.limit_label,
    )


def _district_figures(
    district: District, stats: DistrictStats, f: rules.CityFilters, hotspots: int
) -> rules.DistrictFigures:
    return rules.DistrictFigures(
        name=district.name,
        code=district.code,
        comfort=stats.comfort,
        safety=stats.safety,
        air=stats.air,
        noise=stats.noise,
        surface_index=stats.surface_index,
        rides_week=rules.scale_rides(stats.rides_week, f),
        km_measured=stats.km_measured,
        hotspots=hotspots,
        pm25=stats.pm25,
        db=stats.db,
    )


def _district_stat(d: rules.DistrictFigures) -> api.DistrictStat:
    return api.DistrictStat(
        name=d.name,
        code=d.code,
        scores=Scores(comfort=d.comfort, safety=d.safety, air=d.air, noise=d.noise),
        surface_index=d.surface_index,
        rides_week=d.rides_week,
        km_measured=d.km_measured,
        hotspots=d.hotspots,
        pm25=d.pm25,
        db=d.db,
    )
