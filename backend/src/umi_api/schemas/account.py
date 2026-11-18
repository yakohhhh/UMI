from typing import Literal

from umi_api.schemas.base import ApiModel, IsoDateTime


class Quota(ApiModel):
    used: int
    limit: int
    resets_at: IsoDateTime


class ApiEndpoint(ApiModel):
    method: Literal["GET", "POST"]
    path: str
    description: str


class DailyCalls(ApiModel):
    # YYYY-MM-DD, UTC
    day: str
    calls: int


class ApiUsage(ApiModel):
    key: str
    plan: str
    quota: Quota
    rate_limit: str
    endpoints: list[ApiEndpoint]
    daily: list[DailyCalls]
