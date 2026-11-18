from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import ColumnElement, delete, distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from umi_api.db.models import (
    BrakeHotspot,
    HotspotCauseAnswer,
    Pothole,
    SegmentSurface,
    StreetSegment,
)
from umi_api.domain.aggregation import HourScores
from umi_api.domain.enums import ActivityType, BrakeCause


@dataclass
class CauseTally:
    """Answers per cause at one hotspot, and the distinct riders behind the ones that count."""

    answers: dict[BrakeCause, int] = field(default_factory=dict)
    riders: int = 0


def _creation_order(column: InstrumentedAttribute[str]) -> tuple[ColumnElement[int], InstrumentedAttribute[str]]:
    # Ids are numbered in creation order ("hs-2" before "hs-10").
    return func.length(column), column


class StreetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def segments(self) -> Sequence[StreetSegment]:
        query = (
            select(StreetSegment)
            .options(selectinload(StreetSegment.hourly), selectinload(StreetSegment.district))
            .order_by(StreetSegment.id)
        )
        return (await self._session.scalars(query)).all()

    async def network(self) -> Sequence[StreetSegment]:
        """Every segment with its district, for the map matching index."""
        query = select(StreetSegment).options(selectinload(StreetSegment.district)).order_by(StreetSegment.id)
        return (await self._session.scalars(query)).all()

    async def set_day_scores(self, scores: Mapping[str, HourScores]) -> None:
        """All-day scores per segment id."""
        if scores:
            rows = [{"id": segment_id, **vars(s)} for segment_id, s in scores.items()]
            await self._session.execute(update(StreetSegment), rows)

    async def pothole_counts(self) -> dict[str, int]:
        query = select(Pothole.segment_id, func.count()).group_by(Pothole.segment_id)
        return dict((await self._session.execute(query)).all())

    async def potholes(self) -> Sequence[Pothole]:
        query = select(Pothole).options(selectinload(Pothole.segment)).order_by(*_creation_order(Pothole.id))
        return (await self._session.scalars(query)).all()

    async def surface_ranking(self) -> Sequence[SegmentSurface]:
        """Roughest first."""
        query = (
            select(SegmentSurface)
            .options(selectinload(SegmentSurface.segment).selectinload(StreetSegment.district))
            .order_by(SegmentSurface.surface_index, SegmentSurface.segment_id)
        )
        return (await self._session.scalars(query)).all()


class HotspotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def all(self) -> Sequence[BrakeHotspot]:
        query = (
            select(BrakeHotspot)
            .options(selectinload(BrakeHotspot.district))
            .order_by(*_creation_order(BrakeHotspot.id))
        )
        return (await self._session.scalars(query)).all()

    async def cause_tallies(self, since: datetime, activity_type: ActivityType | None = None) -> dict[str, CauseTally]:
        """Answers given since `since`; "just me" answers are left out of both counts."""
        counted = (HotspotCauseAnswer.answered_at >= since, HotspotCauseAnswer.cause != BrakeCause.JUST_ME)
        mode = () if activity_type is None else (HotspotCauseAnswer.activity_type == activity_type,)
        tallies: dict[str, CauseTally] = defaultdict(CauseTally)
        per_cause = (
            select(HotspotCauseAnswer.hotspot_id, HotspotCauseAnswer.cause, func.count())
            .where(*counted, *mode)
            .group_by(HotspotCauseAnswer.hotspot_id, HotspotCauseAnswer.cause)
        )
        for hotspot_id, cause, answers in await self._session.execute(per_cause):
            tallies[hotspot_id].answers[cause] = answers
        riders = (
            select(HotspotCauseAnswer.hotspot_id, func.count(distinct(HotspotCauseAnswer.rider_key)))
            .where(*counted, *mode)
            .group_by(HotspotCauseAnswer.hotspot_id)
        )
        for hotspot_id, count in await self._session.execute(riders):
            tallies[hotspot_id].riders = count
        return dict(tallies)

    async def record_answer(
        self,
        *,
        hotspot_id: str,
        ride_event_id: str,
        rider_key: str,
        activity_type: ActivityType,
        cause: BrakeCause,
        answered_at: datetime,
    ) -> None:
        """The rider's answer for their own brake at a hotspot; answering again replaces it."""
        answer = await self._session.scalar(
            select(HotspotCauseAnswer).where(HotspotCauseAnswer.ride_event_id == ride_event_id)
        )
        if answer is None:
            answer = HotspotCauseAnswer(ride_event_id=ride_event_id)
            self._session.add(answer)
        answer.hotspot_id = hotspot_id
        answer.rider_key = rider_key
        answer.activity_type = activity_type
        answer.cause = cause
        answer.answered_at = answered_at

    async def delete_answers(self, hotspot_ids: Sequence[str]) -> None:
        await self._session.execute(delete(HotspotCauseAnswer).where(HotspotCauseAnswer.hotspot_id.in_(hotspot_ids)))
