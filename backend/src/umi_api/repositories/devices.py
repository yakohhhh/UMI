from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.db.models import Device


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, device_id: str) -> Device | None:
        return await self._session.get(Device, device_id)

    async def by_serial(self, serial: str) -> Device | None:
        return await self._session.scalar(select(Device).where(Device.serial == serial))

    def add(self, device: Device) -> None:
        self._session.add(device)
