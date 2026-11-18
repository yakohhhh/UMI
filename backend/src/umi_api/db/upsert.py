"""Insert-or-update by primary key without dialect-specific SQL (ADR 0004)."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import insert, inspect, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.db.base import Base


async def upsert(session: AsyncSession, model: type[Base], rows: Sequence[Mapping[str, Any]]) -> None:
    """Update the rows whose primary key exists, insert the others (two bulk statements)."""
    if not rows:
        return
    mapper = inspect(model)
    keys = [mapper.get_property_by_column(column).key for column in mapper.primary_key]
    columns = [getattr(model, key) for key in keys]
    wanted = [tuple(row[key] for key in keys) for row in rows]
    existing: set[tuple[Any, ...]] = set()
    # Chunked: SQLite caps the number of bound parameters per statement.
    for start in range(0, len(wanted), 400):
        chunk = wanted[start : start + 400]
        single = len(columns) == 1
        condition = columns[0].in_([key[0] for key in chunk]) if single else tuple_(*columns).in_(chunk)
        found = await session.execute(select(*columns).where(condition))
        existing.update(tuple(row) for row in found)
    updates = [row for row, key in zip(rows, wanted, strict=True) if key in existing]
    inserts = [row for row, key in zip(rows, wanted, strict=True) if key not in existing]
    if updates:
        await session.execute(update(model), list(updates))
    if inserts:
        await session.execute(insert(model), list(inserts))
