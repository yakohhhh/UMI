from collections.abc import Collection, Sequence
from datetime import datetime

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from umi_api.db.models import Activity, ActivitySegment, Flag, RideEvent
from umi_api.domain.enums import RideEventType

# What a feed card or a ride report shows: events, and flags with their hazard.
_SUMMARY = (
    selectinload(Activity.events),
    selectinload(Activity.flags).selectinload(Flag.hazard),
)
_DETAIL = (
    *_SUMMARY,
    selectinload(Activity.detail),
    selectinload(Activity.segments).selectinload(ActivitySegment.segment),
)


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def by_athletes(self, athlete_ids: Collection[str]) -> Sequence[Activity]:
        """Most recent first."""
        query = (
            select(Activity)
            .where(Activity.athlete_id.in_(athlete_ids))
            .options(*_SUMMARY)
            .order_by(Activity.started_at.desc(), Activity.id)
        )
        return (await self._session.scalars(query)).all()

    async def started_since(self, athlete_id: str, since: datetime) -> Sequence[Activity]:
        """Bare activities (no events or flags loaded), most recent first."""
        query = (
            select(Activity)
            .where(Activity.athlete_id == athlete_id, Activity.started_at >= since)
            .order_by(Activity.started_at.desc(), Activity.id)
        )
        return (await self._session.scalars(query)).all()

    async def get(self, activity_id: str, *, detail: bool = False) -> Activity | None:
        options: tuple[ExecutableOption, ...] = _DETAIL if detail else _SUMMARY
        return await self._session.scalar(select(Activity).where(Activity.id == activity_id).options(*options))

    async def event(self, activity_id: str, event_id: str) -> RideEvent | None:
        """With the street pass that counts it, which a cause re-weighs."""
        query = (
            select(RideEvent)
            .where(RideEvent.activity_id == activity_id, RideEvent.id == event_id)
            .options(selectinload(RideEvent.segment_pass))
        )
        return await self._session.scalar(query)

    async def brakes_in_pass(self, segment_pass_id: int) -> Sequence[RideEvent]:
        query = select(RideEvent).where(
            RideEvent.segment_pass_id == segment_pass_id, RideEvent.type == RideEventType.HARD_BRAKE
        )
        return (await self._session.scalars(query)).all()

    async def flag(self, activity_id: str, flag_id: str) -> Flag | None:
        query = (
            select(Flag).where(Flag.activity_id == activity_id, Flag.id == flag_id).options(selectinload(Flag.hazard))
        )
        return await self._session.scalar(query)

    async def exists(self, activity_id: str) -> bool:
        return bool(await self._session.scalar(select(exists().where(Activity.id == activity_id))))

    async def session_stored(self, device_id: str, session_id: int) -> bool:
        """Whether a Clip session is already an activity (uploaded, or imported with the demo)."""
        stored = exists().where(Activity.device_id == device_id, Activity.session_id == session_id)
        return bool(await self._session.scalar(select(stored)))

    async def flag_times(self, athlete_id: str, since: datetime, until: datetime) -> list[datetime]:
        """When the rider's stored flags were pressed, between two instants."""
        query = (
            select(Flag.pressed_at)
            .join(Activity, Activity.id == Flag.activity_id)
            .where(Activity.athlete_id == athlete_id, Flag.pressed_at >= since, Flag.pressed_at < until)
        )
        return list(await self._session.scalars(query))

    def add(self, activity: Activity) -> None:
        """Stage an activity with its events, flags, segments and detail."""
        self._session.add(activity)

    async def delete(self, activity_ids: Collection[str]) -> None:
        """Remove activities and everything that belongs to them (ON DELETE CASCADE)."""
        await self._session.execute(delete(Activity).where(Activity.id.in_(activity_ids)))
