from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.db.models import ApiKey, ApiUsageDay


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_key(self, account: str) -> ApiKey | None:
        """The account's current key (the newest one not revoked)."""
        query = (
            select(ApiKey)
            .where(ApiKey.account == account, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc())
            .limit(1)
        )
        return await self._session.scalar(query)

    async def usage(self, api_key_id: str, first: date, last: date) -> Sequence[ApiUsageDay]:
        query = (
            select(ApiUsageDay)
            .where(ApiUsageDay.api_key_id == api_key_id, ApiUsageDay.day >= first, ApiUsageDay.day <= last)
            .order_by(ApiUsageDay.day)
        )
        return (await self._session.scalars(query)).all()
