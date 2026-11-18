"""The City API console: key, quota, endpoints and recent usage."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.clock import Clock
from umi_api.repositories.accounts import ApiKeyRepository
from umi_api.schemas.account import ApiEndpoint, ApiUsage, DailyCalls, Quota
from umi_api.services.errors import NotFoundError

USAGE_DAYS = 14

# The public City API (aggregates only, k-anonymous), as documented in the console.
CITY_API_ENDPOINTS = (
    ApiEndpoint(
        method="GET",
        path="/v1/city/segments",
        description="Scored street segments (GeoJSON), filterable by bbox, hour and mode",
    ),
    ApiEndpoint(
        method="GET",
        path="/v1/city/surface/ranking",
        description="Segments ranked by surface index, with confirmed impacts",
    ),
    ApiEndpoint(
        method="GET",
        path="/v1/city/safety/hotspots",
        description="Hard-brake clusters (> 3 m/s²) with counts, peak hours and why riders brake (5+ riders)",
    ),
    ApiEndpoint(
        method="GET",
        path="/v1/city/hazards",
        description="Hazards flagged from riders' Clips (roadworks, blocked lanes, potholes), 5+ riders, day-level",
    ),
    ApiEndpoint(method="GET", path="/v1/city/air-noise", description="PM2.5 and dB(A) by hour × weekday"),
    ApiEndpoint(method="GET", path="/v1/city/districts", description="District aggregates and boundaries"),
)


class AccountService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._clock = clock
        self._keys = ApiKeyRepository(session)

    async def usage(self, account: str) -> ApiUsage:
        key = await self._keys.active_key(account)
        if key is None:
            raise NotFoundError("This account has no active API key")
        now = self._clock.now().astimezone(UTC)
        today = now.date()
        first = today - timedelta(days=USAGE_DAYS - 1)
        calls = {row.day: row.calls for row in await self._keys.usage(key.id, first, today)}
        days = [first + timedelta(days=i) for i in range(USAGE_DAYS)]
        return ApiUsage(
            key=key.token,
            plan=key.plan,
            quota=Quota(used=key.quota_used, limit=key.monthly_quota, resets_at=_next_month(now)),
            rate_limit=f"{key.rate_limit_per_s} requests / second",
            endpoints=list(CITY_API_ENDPOINTS),
            daily=[DailyCalls(day=day.isoformat(), calls=calls.get(day, 0)) for day in days],
        )


def _next_month(now: datetime) -> datetime:
    year, month = divmod(now.year * 12 + now.month, 12)
    return datetime(year, month + 1, 1, tzinfo=UTC)
