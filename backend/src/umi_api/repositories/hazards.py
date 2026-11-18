from collections.abc import Collection, Sequence
from datetime import datetime

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from umi_api.db.models import Hazard, HazardConfirmation
from umi_api.domain.enums import ActivityType, HazardStatus
from umi_api.domain.geo import BBox
from umi_api.domain.hazards import OPEN_STATUSES

_riders = func.count(distinct(HazardConfirmation.rider_key))
# On everyone's street map: verified, or already sent to the city and not fixed or gone.
_LIVE = (HazardStatus.VERIFIED, HazardStatus.SENT_TO_CITY)


class HazardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def rider_counts(self, hazard_ids: Collection[str]) -> dict[str, int]:
        """Distinct riders who flagged or confirmed each hazard."""
        if not hazard_ids:
            return {}
        query = (
            select(HazardConfirmation.hazard_id, _riders)
            .where(HazardConfirmation.hazard_id.in_(hazard_ids))
            .group_by(HazardConfirmation.hazard_id)
        )
        return {hazard_id: riders for hazard_id, riders in await self._session.execute(query)}

    async def open_within(self, bbox: BBox) -> Sequence[Hazard]:
        """Hazards a flag can still join, inside a bounding box."""
        min_lon, min_lat, max_lon, max_lat = bbox
        query = select(Hazard).where(
            Hazard.status.in_(OPEN_STATUSES),
            Hazard.lon.between(min_lon, max_lon),
            Hazard.lat.between(min_lat, max_lat),
        )
        return (await self._session.scalars(query)).all()

    async def get_many(self, hazard_ids: Collection[str]) -> dict[str, Hazard]:
        hazards = await self._session.scalars(select(Hazard).where(Hazard.id.in_(hazard_ids)))
        return {h.id: h for h in hazards}

    async def confirmations_by(self, rider_key: str, hazard_ids: Collection[str]) -> dict[str, HazardConfirmation]:
        """The rider's confirmation of each hazard they already flagged or confirmed."""
        query = select(HazardConfirmation).where(
            HazardConfirmation.rider_key == rider_key, HazardConfirmation.hazard_id.in_(hazard_ids)
        )
        return {c.hazard_id: c for c in await self._session.scalars(query)}

    def add(self, item: Hazard | HazardConfirmation) -> None:
        self._session.add(item)

    async def live(self, min_riders: int) -> list[tuple[Hazard, int]]:
        query = self._with_riders(min_riders).where(Hazard.status.in_(_LIVE), Hazard.kind.is_not(None))
        return await self._fetch(query)

    async def sent_to_city(
        self, min_riders: int, *, confirmed_since: datetime | None = None, activity_type: ActivityType | None = None
    ) -> list[tuple[Hazard, int]]:
        """Hazards in the city's queue. With `activity_type`, only riders on that kind of activity count."""
        query = self._with_riders(min_riders).where(Hazard.city_status.is_not(None), Hazard.kind.is_not(None))
        if confirmed_since is not None:
            query = query.where(Hazard.last_confirmed_at >= confirmed_since)
        if activity_type is not None:
            query = query.where(HazardConfirmation.activity_type == activity_type)
        return await self._fetch(query)

    def _with_riders(self, min_riders: int) -> Select[Hazard, int]:
        return (
            select(Hazard, _riders)
            .join(HazardConfirmation, HazardConfirmation.hazard_id == Hazard.id)
            .group_by(Hazard.id)
            .having(_riders >= min_riders)
            .options(selectinload(Hazard.district))
            .order_by(_riders.desc(), Hazard.id)
        )

    async def _fetch(self, query: Select[Hazard, int]) -> list[tuple[Hazard, int]]:
        return list((await self._session.execute(query)).all())
