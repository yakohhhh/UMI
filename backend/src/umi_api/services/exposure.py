"""PM2.5 and noise a rider breathes and hears while riding."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.clock import Clock
from umi_api.domain.calendar import local_day
from umi_api.domain.exposure import THRESHOLDS, exposure_report
from umi_api.repositories.riders import ExposureRepository
from umi_api.schemas import exposure as api


class ExposureService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._clock = clock
        self._exposure = ExposureRepository(session)

    async def summary(self, athlete_id: str, days: int) -> api.ExposureSummary:
        """The last `days` days, today included."""
        since = local_day(self._clock.now()) - timedelta(days=days - 1)
        rows = await self._exposure.days(athlete_id, since)
        report = exposure_report(rows)
        contributors = await self._exposure.contributors(athlete_id)
        return api.ExposureSummary(
            days=[
                api.ExposureDay(date=d.day, ride_min=d.ride_min, pm25=d.pm25, db=d.db, dose_ug_h=d.dose_ug_h)
                for d in rows
            ],
            weekly=[api.ExposurePeriod.model_validate(p) for p in report.weekly],
            monthly=[api.ExposurePeriod.model_validate(p) for p in report.monthly],
            thresholds=api.ExposureThresholds.model_validate(THRESHOLDS),
            insights=[api.ExposureInsight.model_validate(i) for i in report.insights],
            totals=api.ExposureTotals.model_validate(report.totals),
            contributors=[api.ExposureContributor.model_validate(c) for c in contributors],
        )
