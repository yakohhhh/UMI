from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from umi_api.db.models import SegmentHourlyBaseline, SegmentHourlyScore, SegmentPass
from umi_api.db.upsert import upsert
from umi_api.domain.aggregation import HourScores

# (segment id, local hour)
type SegmentHour = tuple[str, int]


def _among(column: InstrumentedAttribute[str], segment_ids: Collection[str] | None) -> ColumnElement[bool]:
    return true() if segment_ids is None else column.in_(segment_ids)


class StreetScoreRepository:
    """Hourly street scores: the published ones, their seeded baseline, and the passes they are computed from."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def published(self, segment_ids: Collection[str]) -> dict[str, list[HourScores]]:
        """Published scores per segment, indexed by hour."""
        query = (
            select(SegmentHourlyScore)
            .where(SegmentHourlyScore.segment_id.in_(segment_ids))
            .order_by(SegmentHourlyScore.segment_id, SegmentHourlyScore.hour)
        )
        scores: dict[str, list[HourScores]] = defaultdict(list)
        for row in await self._session.scalars(query):
            scores[row.segment_id].append(HourScores(row.comfort, row.safety, row.air, row.noise))
        return dict(scores)

    async def baselines(self, segment_ids: Collection[str] | None = None) -> dict[SegmentHour, HourScores]:
        """Seeded scores per segment and hour; every segment when `segment_ids` is None."""
        query = select(SegmentHourlyBaseline).where(_among(SegmentHourlyBaseline.segment_id, segment_ids))
        return {
            (row.segment_id, row.hour): HourScores(row.comfort, row.safety, row.air, row.noise)
            for row in await self._session.scalars(query)
        }

    async def passes_since(self, since: datetime, segment_ids: Collection[str] | None = None) -> Sequence[SegmentPass]:
        query = select(SegmentPass).where(SegmentPass.hour_start >= since, _among(SegmentPass.segment_id, segment_ids))
        return (await self._session.scalars(query)).all()

    def add_passes(self, passes: Iterable[SegmentPass]) -> None:
        self._session.add_all(passes)

    async def publish(self, scores: Mapping[SegmentHour, HourScores]) -> None:
        rows = [{"segment_id": segment_id, "hour": hour, **vars(s)} for (segment_id, hour), s in scores.items()]
        await upsert(self._session, SegmentHourlyScore, rows)
