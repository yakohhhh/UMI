"""Street scores recomputed from riders' passes (`umi-api aggregate`, and after an upload in development)."""

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.clock import Clock
from umi_api.db.models import SegmentPass
from umi_api.domain.aggregation import WINDOW, HourScores, day_scores, segment_hour_scores
from umi_api.domain.calendar import local_hour
from umi_api.repositories.scores import SegmentHour, StreetScoreRepository
from umi_api.repositories.streets import StreetRepository


@dataclass(frozen=True)
class AggregationReport:
    segments: int
    # Segment-hours whose published scores now include riders' passes.
    from_riders: int
    # Segment-hours with recent passes, but from too few distinct riders to publish them.
    held_back: int


class AggregationService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._clock = clock
        self._scores = StreetScoreRepository(session)
        self._streets = StreetRepository(session)

    async def run(self, segment_ids: Collection[str] | None = None) -> AggregationReport:
        """Publish every hour of the given segments (all of them by default) from the baseline and the passes.

        Every hour is rewritten, not only those with passes: a segment-hour whose passes
        aged out of the window goes back to its baseline. The caller commits.
        """
        baselines = await self._scores.baselines(segment_ids)
        passes: dict[SegmentHour, list[SegmentPass]] = defaultdict(list)
        for p in await self._scores.passes_since(self._clock.now() - WINDOW, segment_ids):
            passes[p.segment_id, local_hour(p.hour_start)].append(p)

        published: dict[SegmentHour, HourScores] = {}
        from_riders = held_back = 0
        for key, baseline in baselines.items():
            scores = segment_hour_scores(baseline, passes[key]) if key in passes else None
            if scores is not None:
                from_riders += 1
            elif key in passes:
                held_back += 1
            published[key] = scores or baseline
        await self._scores.publish(published)

        hours: dict[str, list[HourScores]] = defaultdict(list)
        for (segment_id, _hour), scores in sorted(published.items()):
            hours[segment_id].append(scores)
        await self._streets.set_day_scores({segment_id: day_scores(h) for segment_id, h in hours.items()})
        return AggregationReport(segments=len(hours), from_riders=from_riders, held_back=held_back)
