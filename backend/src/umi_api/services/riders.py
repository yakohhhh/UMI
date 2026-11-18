"""The rider's home screen: who they are, their week, today's best window and their Clip."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.clock import Clock
from umi_api.db.models import Device
from umi_api.domain.week import week_summary
from umi_api.repositories.activities import ActivityRepository
from umi_api.repositories.athletes import AthleteRepository
from umi_api.schemas.athletes import Athlete
from umi_api.schemas.rider import BestWindow, ClipFlagging, ClipSensor, ClipStatus, WeekDay, WeekStats
from umi_api.services.errors import NotFoundError

# The sensors on every Clip, in the order the app lists them.
SENSORS = (
    ("gnss", "GNSS", "Multi-band GPS + Galileo, 1 Hz"),
    ("imu", "IMU · 6-axis", "Vibration & hard brakes, 100 Hz"),
    ("pm", "PM2.5", "Laser particle sensor, every 10 s"),
    (
        "mic",
        "Microphone",
        "dB(A) · one keyword while you hold the button, if voice keywords are on · audio never leaves the Clip",
    ),
    ("env", "Temperature & humidity", "Corrects the PM2.5 reading"),
)
LANGUAGE_NAMES = {"ca": "Català", "es": "Español", "en": "English", "fr": "Français"}
# The phone keeps the Clip's BLE link; until the companion app reports it, a recent sync stands for it.
CONNECTED_WITHIN = timedelta(minutes=15)


class RiderService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._clock = clock
        self._athletes = AthleteRepository(session)
        self._activities = ActivityRepository(session)

    async def athlete(self, athlete_id: str) -> Athlete:
        athlete = await self._athletes.get(athlete_id)
        if athlete is None:
            raise NotFoundError(f"Athlete {athlete_id} not found")
        return Athlete.model_validate(athlete)

    async def week(self, athlete_id: str) -> WeekStats:
        athlete = await self._athletes.get(athlete_id)
        if athlete is None:
            raise NotFoundError(f"Athlete {athlete_id} not found")
        profile = await self._athletes.profile(athlete_id)
        now = self._clock.now()
        # A superset of the current week; week_summary cuts it at Monday, Barcelona time.
        recent = await self._activities.started_since(athlete_id, now - timedelta(days=8))
        week = week_summary(recent, now)
        return WeekStats(
            distance_km=week.distance_km,
            moving_time_s=week.moving_time_s,
            rides=week.rides,
            runs=week.runs,
            goal_km=athlete.weekly_goal_km,
            streak_days=0 if profile is None else profile.streak_days,
            days=[WeekDay.model_validate(day) for day in week.days],
        )

    async def best_window(self, athlete_id: str) -> BestWindow:
        best = await self._athletes.best_window(athlete_id)
        if best is None:
            raise NotFoundError("No best window yet: it needs a few rides on the same trip")
        return BestWindow(
            title=best.title, window=best.time_window, detail=best.detail, metric=best.metric, score=best.score
        )

    async def clip(self, athlete_id: str) -> ClipStatus:
        device = await self._athletes.paired_device(athlete_id)
        if device is None or device.last_sync_at is None:
            raise NotFoundError("No Clip paired with this account yet")
        return ClipStatus(
            name=device.name,
            serial=device.serial,
            battery=device.battery_pct or 0,
            last_sync=device.last_sync_at,
            firmware=device.firmware,
            connected=self._clock.now() - device.last_sync_at <= CONNECTED_WITHIN,
            sensors=_sensors(device),
            flagging=ClipFlagging(
                voice=device.voice_keywords,
                languages=[LANGUAGE_NAMES.get(code, code) for code in device.keyword_languages],
                chirp=device.chirp,
                warn_ahead=device.warn_ahead,
            ),
        )


def _sensors(device: Device) -> list[ClipSensor]:
    return [
        ClipSensor(id=sensor_id, label=label, enabled=sensor_id not in device.disabled_sensors, detail=detail)
        for sensor_id, label, detail in SENSORS
    ]
