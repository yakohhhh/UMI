"""The rider's profile: totals, records, badges, contributions and their impact, clubs."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.db.models import Activity, AthleteProfile, AthleteRecord
from umi_api.domain.calendar import iso_utc, local_day
from umi_api.domain.enums import ActivityType
from umi_api.domain.impact import Impact, impact
from umi_api.domain.numbers import js_round
from umi_api.repositories.activities import ActivityRepository
from umi_api.repositories.athletes import AthleteRepository
from umi_api.repositories.hazards import HazardRepository
from umi_api.schemas import profile as api
from umi_api.schemas.activities import FlagReport
from umi_api.services.activities import ride_flag
from umi_api.services.errors import NotFoundError

TRUST_MAX = 10
# Record kinds in the order the profile shows them; "comfort" is computed from the rides.
RECORD_ORDER = ("longest", "comfort", "calm", "fast")


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._athletes = AthleteRepository(session)
        self._activities = ActivityRepository(session)
        self._hazards = HazardRepository(session)

    async def profile(self, athlete_id: str) -> api.ProfileStats:
        if await self._athletes.get(athlete_id) is None:
            raise NotFoundError(f"Athlete {athlete_id} not found")
        activities = await self._activities.by_athletes([athlete_id])
        snapshot = await self._athletes.profile(athlete_id)
        if snapshot is None:
            if not activities:
                raise NotFoundError("No profile yet: it starts with the first ride")
            snapshot = _from_activities(athlete_id, activities)
        flags = await self._flag_reports(activities)
        earlier = Impact(
            riders_warned=snapshot.earlier_riders_warned,
            verified=snapshot.earlier_verified,
            fixed=snapshot.earlier_fixed,
            causes_given=snapshot.earlier_causes_given,
        )
        outcome = impact(earlier, flags, causes_given=sum(1 for a in activities for e in a.events if e.cause))
        return api.ProfileStats(
            totals=api.ProfileTotals(
                distance_km=snapshot.distance_km,
                rides=snapshot.rides,
                runs=snapshot.runs,
                hours=snapshot.hours,
                streets_mapped=snapshot.streets_mapped,
                since=snapshot.member_since.isoformat(),
            ),
            records=_records(await self._athletes.records(athlete_id), activities),
            badges=[
                api.ProfileBadge(
                    id=b.badge.id,
                    label=b.badge.label,
                    description=b.badge.description,
                    earned=b.earned,
                    progress=b.progress,
                )
                for b in await self._athletes.badges(athlete_id)
            ],
            contributions=api.Contributions(
                streets_improved=snapshot.streets_improved,
                potholes_confirmed=snapshot.potholes_confirmed,
                segments_first=snapshot.segments_first,
                top_streets=[api.TopStreet.model_validate(s) for s in snapshot.top_streets],
                impact=api.Impact.model_validate(outcome),
                trust=api.Trust(
                    level=snapshot.trust_level, max=TRUST_MAX, next=snapshot.trust_next, perks=snapshot.trust_perks
                ),
                flags=flags,
            ),
            clubs=[
                api.ProfileClub(
                    id=m.club.id,
                    name=m.club.name,
                    challenge=m.club.challenge,
                    progress=m.club.progress,
                    goal=m.club.goal,
                    unit=m.club.unit,
                    members=m.club.member_count,
                )
                for m in await self._athletes.clubs(athlete_id)
            ],
        )

    async def _flag_reports(self, activities: Sequence[Activity]) -> list[FlagReport]:
        hazard_ids = {f.hazard_id for a in activities for f in a.flags if f.hazard_id}
        riders = await self._hazards.rider_counts(hazard_ids)
        reports = [
            FlagReport(**ride_flag(f, riders).model_dump(), activity_id=a.id, date=local_day(a.started_at).isoformat())
            for a in activities
            for f in a.flags
        ]
        # Newest day first; on the same day, the later flag first.
        return sorted(reports, key=lambda r: (r.date, r.id), reverse=True)


def _records(stored: Sequence[AthleteRecord], activities: Sequence[Activity]) -> list[api.ProfileRecord]:
    records = [
        api.ProfileRecord(id=r.id, label=r.label, value=r.value, detail=r.detail, date=r.achieved_on.isoformat())
        for r in stored
    ]
    if activities:
        # Most recent first, so the newest ride wins a tie.
        best = max(activities, key=lambda a: a.comfort)
        records.append(
            api.ProfileRecord(
                id="comfort",
                label="Smoothest commute",
                value=f"Comfort {best.comfort}",
                detail=best.title,
                date=iso_utc(best.started_at)[:10],
            )
        )

    def rank(record: api.ProfileRecord) -> int:
        return RECORD_ORDER.index(record.id) if record.id in RECORD_ORDER else len(RECORD_ORDER)

    return sorted(records, key=rank)


def _from_activities(athlete_id: str, activities: Sequence[Activity]) -> AthleteProfile:
    """Figures for a rider the profile job has not processed yet: the stored activities only (unsaved)."""
    return AthleteProfile(
        athlete_id=athlete_id,
        member_since=min(local_day(a.started_at) for a in activities),
        distance_km=js_round(sum(a.distance_m for a in activities) / 100) / 10,
        rides=sum(1 for a in activities if a.type is ActivityType.RIDE),
        runs=sum(1 for a in activities if a.type is ActivityType.RUN),
        hours=js_round(sum(a.moving_time_s for a in activities) / 3600),
        streets_mapped=0,
        streets_improved=0,
        potholes_confirmed=0,
        segments_first=0,
        streak_days=0,
        top_streets=[],
        trust_level=0,
        trust_next="Flag a hazard other riders verify to start building trust",
        trust_perks=[],
        earlier_riders_warned=0,
        earlier_verified=0,
        earlier_fixed=0,
        earlier_causes_given=0,
    )
