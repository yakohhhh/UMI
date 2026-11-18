from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from umi_api.db.models import (
    Athlete,
    AthleteBadge,
    AthleteProfile,
    AthleteRecord,
    Badge,
    BestWindow,
    ClubMembership,
    Device,
    Follow,
)


class AthleteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, athlete_id: str) -> Athlete | None:
        return await self._session.get(Athlete, athlete_id)

    def add(self, athlete: Athlete) -> None:
        self._session.add(athlete)

    async def followee_ids(self, athlete_id: str) -> list[str]:
        rows = await self._session.scalars(select(Follow.followee_id).where(Follow.follower_id == athlete_id))
        return list(rows)

    async def paired_device(self, athlete_id: str) -> Device | None:
        """The rider's Clip; with several, the one that synced last."""
        query = (
            select(Device)
            .where(Device.athlete_id == athlete_id)
            .order_by(Device.last_sync_at.desc().nulls_last(), Device.id)
            .limit(1)
        )
        return await self._session.scalar(query)

    async def best_window(self, athlete_id: str) -> BestWindow | None:
        return await self._session.get(BestWindow, athlete_id)

    async def profile(self, athlete_id: str) -> AthleteProfile | None:
        return await self._session.get(AthleteProfile, athlete_id)

    async def records(self, athlete_id: str) -> Sequence[AthleteRecord]:
        rows = await self._session.scalars(select(AthleteRecord).where(AthleteRecord.athlete_id == athlete_id))
        return rows.all()

    async def badges(self, athlete_id: str) -> Sequence[AthleteBadge]:
        query = (
            select(AthleteBadge)
            .join(Badge)
            .where(AthleteBadge.athlete_id == athlete_id)
            .options(selectinload(AthleteBadge.badge))
            .order_by(Badge.position)
        )
        return (await self._session.scalars(query)).all()

    async def clubs(self, athlete_id: str) -> Sequence[ClubMembership]:
        query = (
            select(ClubMembership)
            .where(ClubMembership.athlete_id == athlete_id)
            .options(selectinload(ClubMembership.club))
            .order_by(ClubMembership.position)
        )
        return (await self._session.scalars(query)).all()
