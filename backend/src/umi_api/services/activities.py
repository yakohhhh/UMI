"""The feed, ride reports, and the answers riders give after a ride."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.clock import Clock
from umi_api.db.models import Activity, Flag, RideEvent
from umi_api.domain.calendar import local_clock_time
from umi_api.domain.enums import BrakeCause, HazardKind, HazardStatus
from umi_api.domain.reports import brake_weight, can_answer_cause, can_answer_kind
from umi_api.repositories.activities import ActivityRepository
from umi_api.repositories.athletes import AthleteRepository
from umi_api.repositories.hazards import HazardRepository
from umi_api.repositories.streets import HotspotRepository
from umi_api.schemas import activities as api
from umi_api.schemas.common import Scores
from umi_api.services.errors import ConflictError, ForbiddenError, NotFoundError


class ActivityService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._activities = ActivityRepository(session)
        self._athletes = AthleteRepository(session)
        self._hazards = HazardRepository(session)
        self._hotspots = HotspotRepository(session)

    async def feed(self, athlete_id: str) -> list[api.ActivitySummary]:
        """The rider's own activities and those of the people they follow, most recent first."""
        visible = [athlete_id, *await self._athletes.followee_ids(athlete_id)]
        activities = await self._activities.by_athletes(visible)
        riders = await self._hazards.rider_counts(_hazard_ids(activities))
        return [summary(a, riders) for a in activities]

    async def detail(self, athlete_id: str, activity_id: str) -> api.ActivityDetail:
        activity = await self._visible(athlete_id, activity_id, detail=True)
        riders = await self._hazards.rider_counts(_hazard_ids([activity]))
        if activity.detail is None:
            raise NotFoundError(f"Activity {activity_id} has no ride report")
        return api.ActivityDetail(
            **_summary_fields(activity, riders),
            route=[(p[0], p[1]) for p in activity.detail.route],
            samples=[(s[0], s[1], s[2], s[3], s[4], s[5], int(s[6])) for s in activity.detail.samples],
            segments=[
                api.ActivitySegment(
                    segment_id=s.segment_id,
                    name=s.segment.name,
                    from_=s.segment.from_name,
                    to=s.segment.to_name,
                    distance_m=s.distance_m,
                    score=s.score,
                    street_average=s.street_average,
                    bike_lane=s.segment.bike_lane,
                )
                for s in activity.segments
            ],
        )

    async def answer_cause(self, athlete_id: str, activity_id: str, event_id: str, cause: BrakeCause) -> None:
        """A cause never deletes the brake: it decides where the event counts."""
        activity = await self._owned(athlete_id, activity_id)
        event = await self._activities.event(activity_id, event_id)
        if event is None:
            raise NotFoundError(f"Event {event_id} is not part of activity {activity_id}")
        if not can_answer_cause(event):
            raise ConflictError("Only the hard brakes the app asks about can be given a cause")
        now = self._clock.now()
        event.cause, event.cause_answered_at = cause, now
        if event.segment_pass is not None:
            # The street's safety counts this brake at the weight its cause gives it.
            brakes = await self._activities.brakes_in_pass(event.segment_pass.id)
            event.segment_pass.weighted_brakes = sum(brake_weight(b.cause) for b in brakes)
        if event.hotspot_id is not None:
            await self._hotspots.record_answer(
                hotspot_id=event.hotspot_id,
                ride_event_id=event.id,
                rider_key=athlete_id,
                activity_type=activity.type,
                cause=cause,
                answered_at=now,
            )
        await self._session.commit()

    async def answer_kind(self, athlete_id: str, activity_id: str, flag_id: str, kind: HazardKind) -> None:
        """What a flag pressed without a keyword was about."""
        await self._owned(athlete_id, activity_id)
        flag = await self._activities.flag(activity_id, flag_id)
        if flag is None:
            raise NotFoundError(f"Flag {flag_id} is not part of activity {activity_id}")
        if not can_answer_kind(flag):
            raise ConflictError("This flag already says what it was: the keyword was recognised on the Clip")
        flag.answered_kind, flag.kind_answered_at = kind, self._clock.now()
        if flag.hazard is not None and flag.hazard.kind is None:
            flag.hazard.kind = kind
        await self._session.commit()

    async def _visible(self, athlete_id: str, activity_id: str, *, detail: bool = False) -> Activity:
        activity = await self._activities.get(activity_id, detail=detail)
        if activity is None or (
            activity.athlete_id != athlete_id
            and activity.athlete_id not in await self._athletes.followee_ids(athlete_id)
        ):
            raise NotFoundError(f"Activity {activity_id} not found")
        return activity

    async def _owned(self, athlete_id: str, activity_id: str) -> Activity:
        activity = await self._visible(athlete_id, activity_id)
        if activity.athlete_id != athlete_id:
            raise ForbiddenError("Only the rider who recorded an activity can answer for it")
        return activity


def summary(activity: Activity, riders: dict[str, int]) -> api.ActivitySummary:
    """`riders`: distinct riders per hazard, for the flags' confirmations."""
    return api.ActivitySummary(**_summary_fields(activity, riders))


def _summary_fields(activity: Activity, riders: dict[str, int]) -> dict[str, Any]:
    return {
        "id": activity.id,
        "athlete_id": activity.athlete_id,
        "type": activity.type,
        "title": activity.title,
        "place": activity.place,
        "description": activity.description,
        "started_at": activity.started_at,
        "duration_s": activity.duration_s,
        "moving_time_s": activity.moving_time_s,
        "distance_m": activity.distance_m,
        "avg_speed_kmh": activity.avg_speed_kmh,
        "max_speed_kmh": activity.max_speed_kmh,
        "elevation_gain_m": activity.elevation_gain_m,
        "scores": Scores(comfort=activity.comfort, safety=activity.safety, air=activity.air, noise=activity.noise),
        "events": [ride_event(e) for e in activity.events],
        "flags": [ride_flag(f, riders) for f in activity.flags],
        "preview": [(p[0], p[1]) for p in activity.preview],
        "kudos": activity.kudos,
        "kudoed_by": activity.kudoed_by,
        "comments": activity.comments,
        "featured": activity.featured,
        "weather": api.Weather(temp_c=activity.weather_temp_c, condition=activity.weather_condition),
    }


def ride_event(event: RideEvent) -> api.RideEvent:
    return api.RideEvent(
        id=event.id,
        type=event.type,
        sample_index=event.sample_index,
        coordinates=(event.lon, event.lat),
        value=event.value,
        time=local_clock_time(event.occurred_at),
        street=event.street,
        cause=event.cause,
        ask=event.ask,
    )


def ride_flag(flag: Flag, riders: dict[str, int]) -> api.RideFlag:
    hazard = flag.hazard
    return api.RideFlag(
        id=flag.id,
        sample_index=flag.sample_index,
        coordinates=(flag.lon, flag.lat),
        time=local_clock_time(flag.pressed_at),
        street=flag.street,
        kind=flag.kind,
        source=flag.source,
        status=HazardStatus.PENDING if hazard is None else hazard.status,
        # Other riders: the hazard's riders include the one who pressed this flag.
        confirmations=0 if hazard is None else max(0, riders.get(hazard.id, 0) - 1),
        riders_warned=0 if hazard is None else hazard.riders_warned,
        proof=None if hazard is None else hazard.proof,
    )


def _hazard_ids(activities: Sequence[Activity]) -> set[str]:
    return {f.hazard_id for a in activities for f in a.flags if f.hazard_id is not None}
