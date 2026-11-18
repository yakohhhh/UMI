from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.db.models import ExposureContributor, ExposureDay, PlannedRoute


class ExposureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def days(self, athlete_id: str, since: date) -> Sequence[ExposureDay]:
        """Oldest first."""
        query = (
            select(ExposureDay)
            .where(ExposureDay.athlete_id == athlete_id, ExposureDay.day >= since)
            .order_by(ExposureDay.day)
        )
        return (await self._session.scalars(query)).all()

    async def day(self, athlete_id: str, day: date) -> ExposureDay | None:
        return await self._session.get(ExposureDay, (athlete_id, day))

    def add(self, day: ExposureDay) -> None:
        self._session.add(day)

    async def contributors(self, athlete_id: str) -> Sequence[ExposureContributor]:
        query = (
            select(ExposureContributor)
            .where(ExposureContributor.athlete_id == athlete_id)
            .order_by(ExposureContributor.position)
        )
        return (await self._session.scalars(query)).all()


class RouteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def planned(self, athlete_id: str) -> Sequence[PlannedRoute]:
        query = select(PlannedRoute).where(PlannedRoute.athlete_id == athlete_id).order_by(PlannedRoute.position)
        return (await self._session.scalars(query)).all()
