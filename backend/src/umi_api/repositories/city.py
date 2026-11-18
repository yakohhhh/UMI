from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from umi_api.db.models import (
    CityAirNoiseCell,
    CityKpi,
    CityMonthlyBrakes,
    CityOutline,
    DatasetSnapshot,
    District,
    Snapshot,
)


class CityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def districts(self) -> Sequence[District]:
        query = select(District).options(selectinload(District.stats)).order_by(District.code)
        return (await self._session.scalars(query)).all()

    async def outlines(self) -> Sequence[CityOutline]:
        return (await self._session.scalars(select(CityOutline).order_by(CityOutline.id))).all()

    async def kpis(self) -> Sequence[CityKpi]:
        return (await self._session.scalars(select(CityKpi).order_by(CityKpi.position))).all()

    async def monthly_brakes(self) -> Sequence[CityMonthlyBrakes]:
        return (await self._session.scalars(select(CityMonthlyBrakes).order_by(CityMonthlyBrakes.month))).all()

    async def air_noise(self) -> list[list[CityAirNoiseCell]]:
        """Weekday x hour, Monday and midnight first."""
        cells = await self._session.scalars(
            select(CityAirNoiseCell).order_by(CityAirNoiseCell.weekday, CityAirNoiseCell.hour)
        )
        matrix: list[list[CityAirNoiseCell]] = []
        for cell in cells:
            if cell.weekday == len(matrix):
                matrix.append([])
            matrix[-1].append(cell)
        return matrix


class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def generated_at(self, name: Snapshot) -> datetime | None:
        snapshot = await self._session.get(DatasetSnapshot, name)
        return None if snapshot is None else snapshot.generated_at
