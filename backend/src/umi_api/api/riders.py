from typing import Annotated

from fastapi import APIRouter, Depends, Query

from umi_api.api.auth import CurrentAthlete
from umi_api.api.deps import ClockDep, SessionDep
from umi_api.schemas.athletes import Athlete
from umi_api.schemas.exposure import ExposureSummary
from umi_api.schemas.profile import ProfileStats
from umi_api.schemas.rider import BestWindow, ClipStatus, WeekStats
from umi_api.services.exposure import ExposureService
from umi_api.services.profile import ProfileService
from umi_api.services.riders import RiderService

router = APIRouter(tags=["rider"])


def _riders(session: SessionDep, clock: ClockDep) -> RiderService:
    return RiderService(session, clock)


Riders = Annotated[RiderService, Depends(_riders)]


@router.get("/me", response_model=Athlete)
async def me(athlete_id: CurrentAthlete, riders: Riders) -> Athlete:
    return await riders.athlete(athlete_id)


@router.get("/athletes/{athlete_id}", response_model=Athlete)
async def athlete(athlete_id: str, _caller: CurrentAthlete, riders: Riders) -> Athlete:
    return await riders.athlete(athlete_id)


@router.get("/me/week", response_model=WeekStats)
async def week(athlete_id: CurrentAthlete, riders: Riders) -> WeekStats:
    """This week, Monday first, in Barcelona time."""
    return await riders.week(athlete_id)


@router.get("/me/best-window", response_model=BestWindow)
async def best_window(athlete_id: CurrentAthlete, riders: Riders) -> BestWindow:
    """Best time slot today for the rider's usual route."""
    return await riders.best_window(athlete_id)


@router.get("/me/clip", response_model=ClipStatus)
async def clip(athlete_id: CurrentAthlete, riders: Riders) -> ClipStatus:
    return await riders.clip(athlete_id)


@router.get("/me/exposure", response_model=ExposureSummary)
async def exposure(
    athlete_id: CurrentAthlete,
    session: SessionDep,
    clock: ClockDep,
    range_: Annotated[str, Query(alias="range", pattern=r"^[1-9]\d{0,3}d$", description="e.g. 365d")] = "365d",
) -> ExposureSummary:
    return await ExposureService(session, clock).summary(athlete_id, days=int(range_.removesuffix("d")))


@router.get("/me/profile", response_model=ProfileStats)
async def profile(athlete_id: CurrentAthlete, session: SessionDep) -> ProfileStats:
    return await ProfileService(session).profile(athlete_id)
