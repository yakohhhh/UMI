from typing import Annotated

from fastapi import APIRouter, Depends

from umi_api.api.auth import CurrentAthlete
from umi_api.api.deps import ClockDep, SessionDep
from umi_api.schemas.activities import ActivityDetail, ActivitySummary, CauseAnswer, KindAnswer
from umi_api.schemas.common import Ok
from umi_api.services.activities import ActivityService

router = APIRouter(tags=["activities"])

_ANSWER_ERRORS: dict[int | str, dict[str, str]] = {
    403: {"description": "Not the rider who recorded the activity"},
    404: {"description": "No such activity, event or flag"},
    409: {"description": "Not a moment the app asks about"},
}


def _activities(session: SessionDep, clock: ClockDep) -> ActivityService:
    return ActivityService(session, clock)


Activities = Annotated[ActivityService, Depends(_activities)]


@router.get("/feed", response_model=list[ActivitySummary])
async def feed(athlete_id: CurrentAthlete, activities: Activities) -> list[ActivitySummary]:
    """The rider's own activities and the people they follow, most recent first."""
    return await activities.feed(athlete_id)


@router.get("/activities/{activity_id}", response_model=ActivityDetail, responses={404: {}})
async def activity(activity_id: str, athlete_id: CurrentAthlete, activities: Activities) -> ActivityDetail:
    return await activities.detail(athlete_id, activity_id)


@router.post("/me/activities/{activity_id}/events/{event_id}/cause", response_model=Ok, responses=_ANSWER_ERRORS)
async def answer_cause(
    activity_id: str, event_id: str, answer: CauseAnswer, athlete_id: CurrentAthlete, activities: Activities
) -> Ok:
    """Why the rider braked, answered after the ride (never while moving)."""
    await activities.answer_cause(athlete_id, activity_id, event_id, answer.cause)
    return Ok()


@router.post("/me/activities/{activity_id}/flags/{flag_id}", response_model=Ok, responses=_ANSWER_ERRORS)
async def answer_kind(
    activity_id: str, flag_id: str, answer: KindAnswer, athlete_id: CurrentAthlete, activities: Activities
) -> Ok:
    """What a flag pressed without a keyword was about."""
    await activities.answer_kind(athlete_id, activity_id, flag_id, answer.kind)
    return Ok()
