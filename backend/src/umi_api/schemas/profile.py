from umi_api.schemas.activities import FlagReport
from umi_api.schemas.base import ApiModel, optional


class ProfileTotals(ApiModel):
    distance_km: float
    rides: int
    runs: int
    hours: int
    streets_mapped: int
    # YYYY-MM-DD
    since: str


class ProfileRecord(ApiModel):
    id: str
    label: str
    value: str
    detail: str
    date: str


class ProfileBadge(ApiModel):
    id: str
    label: str
    description: str
    earned: bool
    progress: float | None = optional()


class TopStreet(ApiModel):
    name: str
    passes: int


class Impact(ApiModel):
    riders_warned: int
    verified: int
    fixed: int
    causes_given: int


class Trust(ApiModel):
    level: int
    max: int
    next: str
    perks: list[str]


class Contributions(ApiModel):
    streets_improved: int
    potholes_confirmed: int
    segments_first: int
    top_streets: list[TopStreet]
    # Outcomes of the rider's flags and answers. Credit follows what happened, never the press itself.
    impact: Impact
    # Private reliability (no leaderboard).
    trust: Trust
    flags: list[FlagReport]


class ProfileClub(ApiModel):
    id: str
    name: str
    challenge: str
    progress: float
    goal: float
    unit: str
    members: int


class ProfileStats(ApiModel):
    totals: ProfileTotals
    records: list[ProfileRecord]
    badges: list[ProfileBadge]
    contributions: Contributions
    clubs: list[ProfileClub]
