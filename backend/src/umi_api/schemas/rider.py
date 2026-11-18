from umi_api.domain.enums import ScoreDimension
from umi_api.schemas.base import ApiModel, IsoDateTime


class WeekDay(ApiModel):
    label: str
    km: float
    is_today: bool


class WeekStats(ApiModel):
    distance_km: float
    moving_time_s: int
    rides: int
    runs: int
    goal_km: float
    streak_days: int
    # Distance per day, Monday first.
    days: list[WeekDay]


class BestWindow(ApiModel):
    title: str
    window: str
    detail: str
    metric: ScoreDimension
    score: int


class ClipSensor(ApiModel):
    id: str
    label: str
    enabled: bool
    detail: str


class ClipFlagging(ApiModel):
    # Hold-to-speak keywords, recognised on the Clip; off by default.
    voice: bool
    languages: list[str]
    # Chirp + LED to confirm a flag (no phone, no earphones).
    chirp: bool
    # Two low chirps when the ride approaches a verified hazard.
    warn_ahead: bool


class ClipStatus(ApiModel):
    name: str
    serial: str
    battery: int
    last_sync: IsoDateTime
    firmware: str
    connected: bool
    sensors: list[ClipSensor]
    flagging: ClipFlagging
